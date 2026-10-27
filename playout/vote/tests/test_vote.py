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


def test_clip_matching_does_not_cross_a_b_takes(tmp_path):
    for n in ("bw-jam-1-clip.mp3", "bw-jam-1b-clip.mp3"):
        (tmp_path / n).write_bytes(b"x")
    assert playlist.find_clip(tmp_path, "bw-jam-1.mp3").name == "bw-jam-1-clip.mp3"
    assert playlist.find_clip(tmp_path, "bw-jam-1b.mp3").name == "bw-jam-1b-clip.mp3"
    assert playlist.find_clip(tmp_path, "bw-jam-2.mp3") is None


def test_no_clips_falls_back_to_songs_without_jams(tmp_path):
    songs = [{"file": "bw-n01.mp3", "group": "fans", "path": Path("x")}, {"file": "bw-jam-1.mp3", "group": "jam", "path": Path("y")}]
    got = playlist.choose_sources(songs, tmp_path)
    assert [s["file"] for s in got] == ["bw-n01.mp3"]


def test_playlist_json_ids_match_audio_prefix():
    cfg = playlist.load()
    assert len(cfg["songs"]) == 31 and len({s["id"] for s in cfg["songs"]}) == 31


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
