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


def test_the_catalog_has_every_full_song_jams_included_and_never_the_shorts_cuts():
    from bwvote import catalog
    cfg = playlist.load()
    got = catalog.load(cfg)
    assert [s["file"] for s in got] == [s["file"] for s in cfg["songs"]]  # all 37 files exist on this machine
    assert sum(s["group"] == "jam" for s in got) == 6
    assert not any("clip" in str(s["path"]) for s in got)


def test_nothing_restarts_the_encoder_but_it_ending_on_its_own():
    src = (Path(__file__).resolve().parent.parent / "run.py").read_text()
    for gone in ("RESCAN_EVERY", "REWEIGHT_EVERY", "new clips ready", "votes changed the weights", "choose_sources"):
        assert gone not in src
    assert src.count("self.launch()") == 2  # the first start, and the relaunch after ffmpeg ends by itself
    assert src.count("self.halt_ffmpeg()") == 1  # only at shutdown
    assert "concat" not in src and "list.txt" not in src  # no fixed song list: the player picks each take as it starts


def test_playlist_json_ids_match_audio_prefix():
    cfg = playlist.load()
    assert len(cfg["songs"]) == 37 and len({s["id"] for s in cfg["songs"]}) == 37


def test_live_timeline_follows_songs_as_they_start():
    from bwvote import pipe
    tl = pipe.LiveTimeline()
    assert not tl
    tl.begin({"title": "Opener"}, 0.0); tl.begin({"title": "Song 1"}, 400.0)
    tl.upcoming = {"title": "Song 2"}
    assert tl.song_at(0)["title"] == "Opener" and tl.song_at(399.9)["title"] == "Opener"
    assert tl.song_at(400)["title"] == "Song 1" and tl.at(450) == (1, 50)
    assert tl.next_song(10)["title"] == "Song 1" and tl.next_song(450)["title"] == "Song 2"


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
    cmd = run.build_cmd(tmp_path / "bg.png", tmp_path, "f.ttf", "x", "flv")
    i = cmd.index(str(tmp_path / "bg.png"))
    assert cmd[i - 8:i] == ["-re", "-f", "image2", "-loop", "1", "-framerate", "5", "-i"]  # -f image2 is what makes ffmpeg re-read the file
    font = Path("~/repos/hub/internship/showcase/art/band-wagon/fonts/LilitaOne-Regular.ttf").expanduser()
    if font.exists():
        from PIL import Image
        Image.new("RGB", (64, 64), "red").save(tmp_path / "c.png")
        background.build(tmp_path / "c.png", font, tmp_path / "bg.png")
        assert Image.open(tmp_path / "bg.png").size == (1280, 720)
        assert [p.name for p in tmp_path.glob("bg*")] == ["bg.png"]  # no half-written file left beside it


# --- the take catalog, the picker, the audio pipe ---------------------------------------------------------------

def _cfg(tmp_path, takes=None, n=3, titles=None):
    import json
    for i in range(1, n + 1):
        (tmp_path / f"bw-n0{i}.mp3").write_bytes(b"x")
    cfg = {"audio_dir": str(tmp_path), "audio_prefix": "band-wagon/", "catalog": str(tmp_path / "takes" / "catalog.json"),
           "songs": [{"file": f"bw-n0{i}.mp3", "title": f"Song {i}", "id": f"band-wagon/bw-n0{i}.mp3",
                      "path": tmp_path / f"bw-n0{i}.mp3"} for i in range(1, n + 1)]}
    if takes is not None:
        (tmp_path / "takes").mkdir(exist_ok=True)
        (tmp_path / "takes" / "catalog.json").write_text(json.dumps(takes))
    if titles is not None:
        (tmp_path / "takes" / "songs.json").write_text(json.dumps(titles))
    return cfg


def _take(tmp_path, song, n, suffix="", kind="story"):
    """A catalog entry shaped exactly as take_factory.py writes it."""
    path = tmp_path / "takes" / song / f"{song}-t{n}{suffix}.mp3"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return {"song": song, "take": f"{song}-t{n}{suffix}", "take_n": n, "style": "slow", "seed": 10001, "bpm": 76,
            "key": "A minor", "seconds": 215.0, "path": str(path), "lufs": -16.1, "kind": kind, "made": "2026-10-28 01:00:00"}


def test_a_take_joins_the_catalog_once_it_has_settled_and_not_while_held_or_unreadable(tmp_path):
    import os
    from bwvote import catalog
    takes = [_take(tmp_path, "story-1", 1), _take(tmp_path, "story-1", 2), _take(tmp_path, "story-1", 3),
             _take(tmp_path, "bike-a", 0, "b", "bike"), _take(tmp_path, "rave-1", 0, kind="rave")]
    takes[2]["hold"] = True
    cfg = _cfg(tmp_path, takes, titles=[{"id": "story-1", "title": "Nell at Millrace Landing"}])
    old = 1_000_000.0
    for t in (takes[0], takes[2], takes[3], takes[4]):
        os.utime(t["path"], (old, old))
    probe = lambda p: 2.0 if "bike" in p.name else 150.0  # the bike take is a 2 s stub
    got = catalog.load(cfg, now=old + 60, probe=probe)
    assert [s["title"] for s in got] == ["Song 1", "Song 2", "Song 3", "Nell at Millrace Landing, take 1", "Rave 1, take 0"]
    # take 2 just written, take 3 held, the stub too short
    assert got[3]["id"] == "band-wagon/takes/story-1-t1" and got[3]["file"] == "story-1-t1.mp3" and got[3]["group"] == "story"
    catalog._probed.clear()  # the stub was probed once and remembered; a file that grew is probed again in real life (new mtime)
    later = [s["title"] for s in catalog.load(cfg, now=time_now() + 60, probe=lambda p: 150.0)]
    assert "Nell at Millrace Landing, take 2" in later and "Bike A, take 0b" in later and not any("take 3" in t for t in later)
    (tmp_path / "x").mkdir()
    assert len(catalog.load(_cfg(tmp_path / "x"))) == 3  # no catalog file: just playlist.json


def time_now():
    import time
    return time.time()


def test_no_take_twice_until_all_have_played_then_a_new_cycle(tmp_path):
    import random
    from bwvote import picker
    songs = [{"id": f"t{i}", "title": str(i)} for i in range(6)]
    p = picker.Picker(tmp_path / "p.json", random.Random(1))
    first = [p.pick(songs, Tally())["id"] for _ in range(6)]
    assert sorted(first) == sorted(s["id"] for s in songs)  # each exactly once
    second = [p.pick(songs, Tally())["id"] for _ in range(6)]
    assert sorted(second) == sorted(first) and second[0] != first[-1]  # a new cycle; no back-to-back at the join
    again = picker.Picker(tmp_path / "p.json", random.Random(2))     # a restart carries on the cycle
    assert again.cycle == p.cycle and again.last == p.last


def test_a_new_take_is_heard_within_a_few_songs_and_liked_ones_come_earlier(tmp_path):
    import random
    from bwvote import picker
    songs = [{"id": f"t{i}", "title": str(i)} for i in range(30)]
    soonest = []
    for seed in range(40):
        p = picker.Picker(tmp_path / f"a{seed}.json", random.Random(seed))
        for _ in range(30 + 10):  # one whole cycle (everything heard once), then 10 songs into the next
            p.pick(songs, Tally())
        songs2 = songs + [{"id": "new", "title": "new"}]
        soonest.append([p.pick(songs2, Tally())["id"] for _ in range(20)].index("new"))
    assert sum(soonest) / len(soonest) < 6 and max(soonest) < 20  # it lands mid-cycle, and is on air in the next few songs (an even draw would average 10)
    liked = _tally_with([("t0", 6, 0), ("t1", 0, 4)])
    pos = {"t0": [], "t1": []}
    for seed in range(60):
        p = picker.Picker(tmp_path / f"b{seed}.json", random.Random(seed))
        order = [p.pick(songs, liked)["id"] for _ in range(30)]
        for k in pos:
            pos[k].append(order.index(k))
    assert sum(pos["t0"]) < sum(pos["t1"])  # voted up earlier than voted down, in the same cycle


def test_voted_down_takes_rest_a_cycle_now_and_then_but_are_never_dropped(tmp_path):
    import random
    from bwvote import picker
    songs = [{"id": f"t{i}", "title": str(i)} for i in range(4)]
    down = _tally_with([("t0", 0, 4)])  # weight 0.25
    p = picker.Picker(tmp_path / "p.json", random.Random(3))
    plays = [p.pick(songs, down)["id"] for _ in range(40)]
    assert 0 < plays.count("t0") < plays.count("t1")  # rarer, not gone
    assert plays.count("t1") >= 9


def test_the_pipe_carries_song_after_song_gaplessly_and_skips_one_that_will_not_decode(tmp_path):
    import io
    from bwvote import pipe
    tl, sink, picks = pipe.LiveTimeline(), io.BytesIO(), []
    songs = [{"id": f"s{i}", "title": f"S{i}", "path": tmp_path / f"s{i}.pcm"} for i in range(4)]
    for s in songs[:3]:
        s["path"].write_bytes(b"\x01\x00" * 48000 * 2 * 2)  # 2 s of raw sound
    bad = songs[3]
    order = iter([songs[1], bad, songs[2]])
    def choose():
        try:
            return next(order)
        except StopIteration:
            f.stop.set(); return songs[0]
    decoder = lambda path: ["cat", str(path)]
    f = pipe.Feeder(sink, tl, choose, first=songs[0], decoder=decoder, log=picks.append)
    f.run()
    assert [s["id"] for s in tl.songs[:3]] == ["s0", "s1", "s2"]  # the one that would not decode left no trace in the timeline
    assert any("skipped s3" in m for m in picks)
    assert tl.starts[:3] == [0.0, 2.0, 4.0]  # exact: every byte counted, no gap and no overlap
    assert f.started.is_set() and tl.upcoming is not None


def test_a_factory_take_s_votes_also_count_toward_its_song_for_the_factory_to_steer_by(tmp_path):
    from bwvote import catalog
    cfg = _cfg(tmp_path, [_take(tmp_path, "story-1", 1), _take(tmp_path, "story-1", 2)])
    import os
    for t in (tmp_path / "takes" / "story-1").iterdir():
        os.utime(t, (1_000_000.0, 1_000_000.0))
    songs = catalog.load(cfg, now=1_000_100.0, probe=lambda p: 150.0)[3:]
    t = Tally()
    t.vote(songs[0]["id"], "a", "up"); t.vote(songs[0]["id"], "b", "up"); t.vote(songs[1]["id"], "a", "down")
    out = t.export(songs)["songs"]
    assert out["band-wagon/takes/story-1-t1"]["up"] == 2
    assert out["story-1"]["up"] == 2 and out["story-1"]["down"] == 1
