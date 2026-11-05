"""narration.py: long pauses shrink to PAUSE, the boundary times move with them, speech is kept intact."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from playout.tutorials import narration as n  # noqa: E402


def test_parse_and_plan():
    log = "silence_start: 2.5\nsilence_end: 3.5 | silence_duration: 1\nsilence_start: 7\nsilence_end: 7.4 | silence_duration: 0.4\n"
    s = n.parse_silences(log)
    assert s == [(2.5, 3.5), (7.0, 7.4)]
    cuts = n.plan_cuts(s)                       # only the 1 s one is cut, down to 0.3 s: 0.7 s removed from its middle
    assert len(cuts) == 1 and abs((cuts[0][1] - cuts[0][0]) - 0.7) < 1e-9
    assert abs(sum(b - a for a, b in cuts) - 0.7) < 1e-9


def test_remap_moves_times_by_what_was_cut_before_them():
    cuts = [(2.65, 3.35)]
    assert n.remap(1.0, cuts) == 1.0
    assert abs(n.remap(4.0, cuts) - 3.3) < 1e-9
    assert abs(n.remap(3.0, cuts) - 2.65) < 1e-9  # inside the cut: lands where the cut starts


def test_keep_ranges_cover_everything_but_the_cuts():
    r = n.keep_ranges([(2.0, 3.0), (5.0, 6.0)], 10.0)
    assert r == [(0.0, 2.0), (3.0, 5.0), (6.0, 10.0)]


def test_remap_boundaries():
    b = [{"offset": int(4.0 * n.TICKS), "duration": int(1.0 * n.TICKS), "text": "x"}]
    out = n.remap_boundaries(b, [(2.65, 3.35)])
    assert abs(out[0]["offset"] / n.TICKS - 3.3) < 1e-6 and out[0]["text"] == "x"


def make_audio(path):
    """tone 1 s, silence 1 s, tone 1 s, silence 0.3 s, tone 1 s (a short pause that must stay)."""
    fc = ("sine=f=440:d=1[a];anullsrc=r=24000:cl=mono,atrim=duration=1[s];sine=f=660:d=1[b];anullsrc=r=24000:cl=mono,atrim=duration=0.3[t];"
          "sine=f=880:d=1[c];[a][s][b][t][c]concat=n=5:v=0:a=1[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-filter_complex", fc,
                    "-map", "[o]", "-t", "4.3", "-c:a", "libmp3lame", str(path)], check=True)


def test_tighten_shortens_the_long_pause_only(tmp_path):
    src, dest = tmp_path / "a.mp3", tmp_path / "b.mp3"
    make_audio(src)
    before = n.probe_duration(src)
    cuts = n.tighten(src, dest)
    after = n.probe_duration(dest)
    assert len(cuts) == 1                               # the 0.3 s pause is below MIN_CUT, kept as it was
    assert abs((before - after) - 0.7) < 0.12           # 1 s pause became 0.3 s (mp3 frame rounding allowed)
    log = n.run_ffmpeg(["-i", str(dest), "-af", "silencedetect=n=-50dB:d=0.2", "-f", "null", "-"]).stderr
    gaps = [e - s for s, e in n.parse_silences(log)]
    assert gaps and max(gaps) < 0.45                    # no pause over 0.45 s is left


def test_speak_asks_again_after_a_failure(monkeypatch, tmp_path):
    import asyncio

    calls = []

    async def flaky(text, voice):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("No audio was received")
        return b"abc", [{"offset": 0, "duration": 1, "text": "hi"}]

    monkeypatch.setattr(n, "speak_once", flaky)
    out = tmp_path / "a.mp3"
    b = asyncio.run(n.speak("hi", str(out), "v", None, tries=4, wait=0))
    assert len(calls) == 3 and out.read_bytes() == b"abc" and b[0]["text"] == "hi"


def test_speak_gives_up_after_the_last_try(monkeypatch, tmp_path):
    import asyncio

    import pytest

    async def dead(text, voice):
        raise RuntimeError("no audio")

    monkeypatch.setattr(n, "speak_once", dead)
    with pytest.raises(RuntimeError):
        asyncio.run(n.speak("hi", str(tmp_path / "a.mp3"), "v", None, tries=2, wait=0))
