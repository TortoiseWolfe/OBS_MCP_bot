import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bwvote import gaps  # noqa: E402


def make(path, gap_at=None, gap_len=0.2):
    expr = "sin(2*PI*440*t)*0.5"
    if gap_at is not None:
        expr = f"if(between(t,{gap_at},{gap_at + gap_len}),0,{expr})"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=22050:d=6", str(path)], check=True)


def test_finds_a_short_gap_inside(tmp_path):
    f = tmp_path / "gap.wav"
    make(f, 3.0, 0.2)
    found, total = gaps.detect(f)
    inside = gaps.inside(found, total)
    assert len(inside) == 1 and abs(inside[0][0] - 3.0) < 0.05 and abs(inside[0][1] - inside[0][0] - 0.2) < 0.05


def test_clean_file_has_none(tmp_path):
    f = tmp_path / "clean.wav"
    make(f)
    found, total = gaps.detect(f)
    assert gaps.inside(found, total) == []


def test_gap_under_the_limit_is_ignored(tmp_path):
    f = tmp_path / "short.wav"
    make(f, 3.0, 0.1)
    found, total = gaps.detect(f)
    assert gaps.inside(found, total) == []
