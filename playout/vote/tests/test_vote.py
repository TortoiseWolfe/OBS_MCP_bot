import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # playout/

import chat_tally as chat
from bwvote import playlist
from bwvote.tally import Tally, parse_command

SONGS = [{"id": f"band-wagon/bw-n0{i}.mp3", "file": f"bw-n0{i}.mp3", "title": f"Song {i}", "seconds": 40.0} for i in range(1, 4)]


def test_parse_command():
    assert parse_command("!up") == "up"
    assert parse_command("  !DOWN please") == "down"
    assert parse_command("up") is None
    assert parse_command("hello !up") is None
    assert parse_command("!up" + "x" * 300) is None


def test_privmsg():
    line = ":Viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #turtlewolfe :!up"
    assert chat.parse_privmsg(line) == ("viewer", "!up")
    assert chat.parse_privmsg("PING :tmi.twitch.tv") is None
    assert chat.parse_privmsg("@badges=;id=1 " + line) == ("viewer", "!up")


def test_latest_vote_counts_and_no_names_stored():
    t = Tally()
    t.vote("a", "Alice", "up"); t.vote("a", "alice", "down"); t.vote("a", "bob", "up")
    assert t.counts("a") == (1, 1)
    assert "alice" not in str(t.state()).lower()
    assert t.viewers() == 2


def test_rankings_and_export():
    t = Tally()
    for u in "abc":
        t.vote(SONGS[0]["id"], u, "up")
    t.vote(SONGS[1]["id"], "a", "down")
    assert t.top_up(SONGS)[0][0]["title"] == "Song 1"
    assert t.top_down(SONGS)[0][0]["title"] == "Song 2"
    ex = t.export(SONGS)
    assert ex["source"] == "twitch" and ex["songs"][SONGS[0]["id"]]["up"] == 3
    assert "top 5 up" in t.report_line(SONGS)


def test_timeline_wraps():
    tl = playlist.Timeline(SONGS)
    assert tl.length == 120 and tl.song_at(0)["title"] == "Song 1"
    assert tl.song_at(40)["title"] == "Song 2" and tl.song_at(125)["title"] == "Song 1"
    assert tl.next_song(119)["title"] == "Song 1"


def test_the_stream_plays_every_full_song_jams_included_and_never_the_shorts_cuts(tmp_path):
    cfg = playlist.load()
    clips = tmp_path / "clips"; clips.mkdir()
    (clips / "bw-n01-clip.mp3").write_bytes(b"x" * 10)  # a Shorts cut exists; it must not be picked
    got = playlist.full_songs(cfg["songs"])
    assert [s["file"] for s in got] == [s["file"] for s in cfg["songs"]]
    assert sum(s["group"] == "jam" for s in got) == 6 and all(s["path"].name == s["file"] for s in got)
    assert not any("clip" in str(s["path"]) for s in got)


def test_nothing_restarts_the_encoder_but_it_ending_on_its_own():
    src = (Path(__file__).resolve().parent.parent / "run.py").read_text()
    for gone in ("RESCAN_EVERY", "REWEIGHT_EVERY", "new clips ready", "votes changed the weights", "choose_sources"):
        assert gone not in src
    assert src.count("self.launch()") == 2  # the first start, and the relaunch after ffmpeg ends by itself
    assert src.count("self.halt_ffmpeg()") == 1  # only at shutdown


def test_playlist_json_ids_match_audio_prefix():
    cfg = playlist.load()
    assert len(cfg["songs"]) == 37 and len({s["id"] for s in cfg["songs"]}) == 37


def test_opener_plays_once_then_the_loop():
    op = {"title": "Opener", "seconds": 400, "opener": True}
    tl = playlist.Timeline(SONGS, lead=[op])
    assert tl.song_at(0)["title"] == "Opener" and tl.song_at(399)["title"] == "Opener"
    assert tl.song_at(400)["title"] == "Song 1" and tl.song_at(400 + 120)["title"] == "Song 1"
    assert tl.next_song(10)["title"] == "Song 1" and tl.next_song(400 + 119)["title"] == "Song 1"
    assert tl.length == 120


def _tally_with(votes):
    t = Tally()
    for song, n_up, n_down in votes:
        for k in range(n_up):
            t.vote(song, f"up{k}", "up")
        for k in range(n_down):
            t.vote(song, f"dn{k}", "down")
    return t


def test_weights_follow_the_votes():
    from bwvote import weights
    assert weights.weight(0, 0) == 1.0 and weights.weight(1, 0) == 1.0  # one stray vote moves nothing
    assert weights.weight(3, 0) == 2.5 and weights.weight(9, 0) == 3.0
    assert weights.weight(0, 2) == 0.25 and weights.weight(0, 9) == 0.25


def test_sequence_plays_liked_more_and_voted_down_less_and_never_back_to_back():
    from bwvote import weights
    t = _tally_with([(SONGS[0]["id"], 4, 0), (SONGS[2]["id"], 0, 3)])
    seq = [s["id"] for s in weights.sequence(SONGS, t, rounds=8)]
    assert seq.count(SONGS[1]["id"]) == 8
    assert seq.count(SONGS[0]["id"]) == 24 and seq.count(SONGS[2]["id"]) == 2
    many = [dict(SONGS[0], id=f"x/{i}", file=f"{i}.mp3") for i in range(8)]  # a short list can't avoid repeats; a real one can
    t2 = _tally_with([("x/0", 6, 0), ("x/7", 0, 3)])
    seq2 = [s["id"] for s in weights.sequence(many, t2, rounds=12)]
    assert seq2.count("x/0") > 2 * seq2.count("x/1") > 2 * seq2.count("x/7")
    assert all(a != b for a, b in zip(seq2, seq2[1:]))


def test_sequence_continues_after_the_song_that_was_playing():
    from bwvote import weights
    seq = weights.sequence(SONGS, Tally(), rounds=2, after_id=SONGS[1]["id"])
    assert seq[0]["id"] == SONGS[2]["id"]


def test_votes_are_logged_with_the_clock_and_song(tmp_path):
    from bwvote.tally import append_jsonl
    append_jsonl(tmp_path / "v.jsonl", {"epoch": 1.0, "vote": "up"})
    append_jsonl(tmp_path / "v.jsonl", {"epoch": 2.0, "vote": "down"})
    assert (tmp_path / "v.jsonl").read_text().count("\n") == 2


def test_featured_songs_keep_a_floor_until_the_date_then_follow_the_votes():
    from datetime import datetime, timezone
    from bwvote import weights
    feat = {"weight": 1, "until": "2026-10-29T12:00:00-04:00"}
    songs = [dict(SONGS[0], feature=feat), SONGS[1], SONGS[2]]
    t = Tally()
    for who in ("a", "b", "c", "d"):  # four voters vote the featured song and song 2 down
        t.vote(songs[0]["id"], who, "down"); t.vote(songs[1]["id"], who, "down")
    before, after = datetime(2026, 10, 28, tzinfo=timezone.utc), datetime(2026, 10, 30, tzinfo=timezone.utc)
    w_before, w_after = weights.weights(songs, t, before), weights.weights(songs, t, after)
    assert w_before[songs[0]["id"]] == 1.0 and w_before[songs[1]["id"]] == 0.25  # the floor holds only the featured one
    assert w_after[songs[0]["id"]] == 0.25
    seq = [s["id"] for s in weights.sequence(songs, t, rounds=4, now=before)]
    assert seq.count(songs[0]["id"]) == 4 and all(a != b for a, b in zip(seq, seq[1:]))
    assert weights.signature(songs, t, before) != weights.signature(songs, t, after)  # expiry restarts the order


def test_playlist_features_the_six_story_takes_until_thursday_noon():
    cfg = playlist.load()
    story = [s for s in cfg["songs"] if s["group"] == "story"]
    assert [s["file"] for s in story] == [f"bw-story-{n}.mp3" for n in ("1", "1b", "7", "7b", "13", "13b")]
    assert all(s["feature"] == {"weight": 2, "until": "2026-10-29T12:00:00-04:00"} for s in story)


def test_viewer_log_rows_share_the_play_clock_format(tmp_path):
    import json, threading
    from bwvote import viewers
    stop, calls = threading.Event(), []

    def get(channel):
        calls.append(channel); stop.set(); return 7

    viewers.run("turtlewolfe", tmp_path / "viewers.jsonl", stop, every=0, get=get)
    r = json.loads((tmp_path / "viewers.jsonl").read_text())
    assert calls == ["turtlewolfe"] and r["channel"] == "turtlewolfe" and r["viewers"] == 7
    assert set(r) == {"epoch", "time", "channel", "viewers"}  # same epoch and time keys as plays.jsonl


def test_viewer_fetch_gives_a_number_or_none(monkeypatch):
    import io
    from bwvote import viewers
    for body, want in ((b"12", 12), (b"0", 0), (b"turtlewolfe is offline", None)):
        monkeypatch.setattr(viewers.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(body))
        assert viewers.fetch("turtlewolfe") == want


def test_announcement_shows_only_inside_its_window_and_playlist_points_to_scripthammer():
    from datetime import datetime, timezone
    from bwvote import overlay
    cfg = playlist.load()
    a = cfg["announcements"]
    inside = datetime(2026, 10, 29, 21, 10, tzinfo=timezone.utc)  # 5:10 PM Eastern (daylight time)
    assert "twitch.tv/scripthammer" in overlay.active_announcement(a, inside)
    assert overlay.active_announcement(a, datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc)) is None  # 4:00 PM
    assert overlay.active_announcement(a, datetime(2026, 10, 29, 21, 30, tzinfo=timezone.utc)) is None  # 5:30 PM: stopped by then
    assert overlay.active_announcement(None, inside) is None


def test_render_puts_the_announcement_on_the_note_line(tmp_path):
    from bwvote import overlay
    song = {"id": "x", "title": "T"}
    overlay.render(tmp_path, song, song, Tally(), [song], "6 PM show: twitch.tv/scripthammer")
    assert (tmp_path / "note.txt").read_text() == "6 PM show: twitch.tv/scripthammer"
    overlay.render(tmp_path, song, song, Tally(), [song])
    assert (tmp_path / "note.txt").read_text() == " "


def test_each_song_gets_its_own_cover_and_falls_back_to_the_show_cover(tmp_path):
    from PIL import Image
    from bwvote import covers
    for n in ("a.png", "default.png"):
        Image.new("RGB", (8, 8)).save(tmp_path / n)
    (tmp_path / "song-covers.json").write_text('{"bw-n01.mp3": "a.png", "bw-n02": "/nowhere/gone.png"}')
    found = covers.load(tmp_path / "song-covers.json")
    assert covers.cover_for(SONGS[0], found, tmp_path / "default.png") == tmp_path / "a.png"      # its own, path beside the json
    assert covers.cover_for(SONGS[1], found, tmp_path / "default.png") == tmp_path / "default.png"  # listed, file missing
    assert covers.cover_for(SONGS[2], found, tmp_path / "default.png") == tmp_path / "default.png"  # not listed
    assert covers.load(tmp_path / "missing.json") == {}                                              # no file yet: everything uses the default
    (tmp_path / "bad.json").write_text("{nope")
    assert covers.load(tmp_path / "bad.json") == {}


def test_the_picture_is_re_read_every_frame_and_replaced_whole(tmp_path):
    import run
    from bwvote import background
    cmd = run.build_cmd(tmp_path / "bg.png", "l.txt", tmp_path, "f.ttf", "x", "flv")
    i = cmd.index(str(tmp_path / "bg.png"))
    assert cmd[i - 8:i] == ["-re", "-f", "image2", "-loop", "1", "-framerate", "5", "-i"]  # -f image2 is what makes ffmpeg re-read the file
    font = Path("~/repos/hub/internship/showcase/art/band-wagon/fonts/LilitaOne-Regular.ttf").expanduser()
    if font.exists():
        from PIL import Image
        Image.new("RGB", (64, 64), "red").save(tmp_path / "c.png")
        background.build(tmp_path / "c.png", font, tmp_path / "bg.png")
        assert Image.open(tmp_path / "bg.png").size == (1280, 720)
        assert [p.name for p in tmp_path.glob("bg*")] == ["bg.png"]  # no half-written file left beside it
