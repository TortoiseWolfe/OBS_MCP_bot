import subprocess

import pytest

from playout.tutorials import bed


def test_gain_moves_measured_loudness_to_target():
    assert bed.section_gain_db(-16.0) == pytest.approx(-10.0)
    assert bed.section_gain_db(-30.0, target=-26.0) == pytest.approx(4.0)


def test_filter_places_the_closing_bed_at_the_end_and_leaves_the_lesson_alone():
    g = bed.bed_filter(total=100.0, lead=15.1, tail=10.05, lead_gain=-10.0, tail_gain=-11.0, tail_start=150.0)
    assert "[0:a]" in g and "atrim=start=150.000:duration=10.050" in g
    assert "adelay=89950:all=1" in g  # 100 - 10.05 s
    assert "amix=inputs=3:normalize=0" in g  # sum, no automatic ducking of the lesson audio
    assert "afade=t=in:st=0:d=1.0" in g and "afade=t=out:st=14.100:d=1.0" in g
    assert g.count("apad=whole_dur=100.000") == 2


def test_refuses_a_window_that_already_has_sound(tmp_path, monkeypatch):
    monkeypatch.setattr(bed, "duration", lambda p: 60.0)
    monkeypatch.setattr(bed, "window_level_db", lambda p, s, n: -30.0)
    with pytest.raises(SystemExit):
        bed.add_bed("a.mp4", str(tmp_path / "o.mp4"), "t.mp3", 15.0, 10.0)


def test_bed_changes_only_the_silent_ends(tmp_path):
    """A real 40 s file: 3 s silent, 34 s tone, 3 s silent. The tone must keep its level, the ends must gain the bed."""
    src, track, out = tmp_path / "s.mp4", tmp_path / "t.wav", tmp_path / "o.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x240:r=30:d=40",
                    "-f", "lavfi", "-i", "sine=f=440:d=34", "-filter_complex",
                    "[1:a]aformat=channel_layouts=stereo,adelay=3000:all=1,apad=whole_dur=40[a]", "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=60", str(track)], check=True)
    r = bed.add_bed(src, out, track, lead=3.0, tail=3.0, lead_start=0.0, tail_start=10.0, bed_lufs=-26.0)
    assert r["seconds"] == pytest.approx(40.0, abs=0.1)
    assert bed.window_level_db(out, 0.0, 0.9) > -80  # bed is audible at the start (fade in covers the first second)
    assert bed.window_level_db(out, 1.0, 1.0) > bed.window_level_db(src, 1.0, 1.0)
    assert abs(bed.window_level_db(out, 10, 20) - bed.window_level_db(src, 10, 20)) < 0.5


def test_filter_adds_a_whole_file_bed_only_when_asked():
    plain = bed.bed_filter(total=100.0, lead=15.0, tail=10.0, lead_gain=-10.0, tail_gain=-11.0)
    assert "amix=inputs=3" in plain and "[bedM]" not in plain
    g = bed.bed_filter(total=100.0, lead=15.0, tail=10.0, lead_gain=-10.0, tail_gain=-11.0, mid_gain=-18.0, mid_start=5.0)
    assert "[3:a]atrim=start=5.000:duration=100.000" in g and "volume=-18.000dB" in g
    assert "[bedM0][sc]sidechaincompress=" in g and "asplit=2[main][sc]" in g
    assert "[main][bedA][bedB][bedM]amix=inputs=4:normalize=0" in g


def test_under_lesson_fills_the_gaps_between_sentences_and_keeps_the_narration_level(tmp_path):
    """3 s silent, tone 3-10 s, 4 s of digital silence (a gap), tone 14-37 s, 3 s silent: the gap must stop being silent."""
    src, track, out = tmp_path / "s.mp4", tmp_path / "t.wav", tmp_path / "o.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x240:r=30:d=40",
                    "-f", "lavfi", "-i", "sine=f=440:d=7", "-f", "lavfi", "-i", "sine=f=440:d=23", "-filter_complex",
                    "[1:a]aformat=channel_layouts=stereo,adelay=3000:all=1,apad=whole_dur=14[x];"
                    "[2:a]aformat=channel_layouts=stereo[y];[x][y]concat=n=2:v=0:a=1,apad=whole_dur=40[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=60", str(track)], check=True)
    assert bed.window_level_db(src, 11.0, 2.0) < -60
    r = bed.add_bed(src, out, track, lead=3.0, tail=3.0, lead_start=0.0, tail_start=10.0, under_lesson=True, mid_lufs=-25.0, tolerance=99)
    assert r["mid_gain_db"] is not None
    assert bed.window_level_db(out, 11.0, 2.0) > -50  # the gap now carries the quiet bed
    assert abs(bed.window_level_db(out, 5, 4) - bed.window_level_db(src, 5, 4)) < 1.0  # the narration keeps its level
