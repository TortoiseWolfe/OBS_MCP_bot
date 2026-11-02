"""rotate.py: choosing the next item from a list that can change, and a real two-item run into a local file."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from playout.tutorials import rotate  # noqa: E402

ALL = lambda p: True  # noqa: E731


def items(*names):
    return [{"path": n, "title": n} for n in names]


def test_first_pick_is_top_then_follows_order_and_wraps():
    it = items("a", "b", "c")
    assert rotate.pick_next(it, None, ALL)["path"] == "a"
    assert rotate.pick_next(it, "a", ALL)["path"] == "b"
    assert rotate.pick_next(it, "c", ALL)["path"] == "a"


def test_changed_list_continues_after_the_playing_item_or_restarts_at_top():
    assert rotate.pick_next(items("a", "x", "b"), "a", ALL)["path"] == "x"      # new item inserted after the one playing
    assert rotate.pick_next(items("x", "y"), "gone", ALL)["path"] == "x"        # playing item removed from the list


def test_missing_files_are_skipped_and_all_missing_gives_none():
    it = items("a", "b", "c")
    assert rotate.pick_next(it, "a", lambda p: p != "b")["path"] == "c"
    assert rotate.pick_next(it, "a", lambda p: False) is None
    assert rotate.pick_next([], None, ALL) is None


def test_bad_list_keeps_the_last_good_one(tmp_path):
    f = tmp_path / "list.json"
    good = items("a")
    for body in ("", "{not json", '{"items": []}', '{"items": 5}', '{"other": 1}'):
        f.write_text(body)
        assert rotate.load_list(f, good) == good
    assert rotate.load_list(tmp_path / "missing.json", good) == good
    f.write_text(json.dumps({"items": items("b", "c") + ["junk", {"title": "no path"}]}))
    assert [i["path"] for i in rotate.load_list(f, good)] == ["b", "c"]


def test_no_key_or_address_in_commands():
    cmd = " ".join(rotate.receiver_cmd("rtmp://127.0.0.1:19350/relay/air") + rotate.feeder_cmd("x.mp4", 3.0))
    assert "live.twitch.tv" not in cmd and "key" not in cmd.lower()


def clip(path, seconds, tone):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=320x180:r=30:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f={tone}:r=48000:d={seconds}", "-c:v", "libx264", "-g", "60", "-keyint_min", "60",
                    "-sc_threshold", "0", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(path)], check=True, timeout=60)


def packets(path, kind):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", kind, "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True, timeout=60)
    return [float(x.split(",")[0]) for x in r.stdout.split() if x]


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="ffmpeg missing")
def test_two_items_join_with_continuous_timestamps(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    clip(a, 3, 440)
    clip(b, 3, 880)
    lst = tmp_path / "list.json"
    lst.write_text(json.dumps({"items": items(str(a), str(b))}))
    out = tmp_path / "out.flv"
    assert rotate.run(str(lst), str(out), "flv", max_items=2) == 0
    st = json.loads((tmp_path / "status.json").read_text())
    assert st["now"] == str(b) and st["played"] == 1
    for kind, step in (("v", 1 / 30), ("a", 0.05)):
        t = sorted(packets(out, kind))
        gaps = [y - x for x, y in zip(t, t[1:])]
        assert max(gaps) < step * 3, (kind, max(gaps))     # no hole at the join
        assert 5.8 < t[-1] - t[0] < 6.3
    from playout.tutorials import airproof
    assert airproof.dts_steps_back(out, "v") == 0 and airproof.dts_steps_back(out, "a") == 0   # the join must not overlap


def test_airproof_windows_are_kbps():
    from playout.tutorials import airproof
    pk = [(float(t), 12500, False) for t in range(0, 30)]      # 12500 bytes a second = 100 kbps
    assert airproof.windows(pk) == [100.0, 100.0]
