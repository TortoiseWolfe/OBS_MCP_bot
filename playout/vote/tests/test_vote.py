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
    assert len(cfg["songs"]) == 27 and len({s["id"] for s in cfg["songs"]}) == 27


def test_opener_plays_once_then_the_loop():
    op = {"title": "Opener", "seconds": 400, "opener": True}
    tl = playlist.Timeline(SONGS, lead=[op])
    assert tl.song_at(0)["title"] == "Opener" and tl.song_at(399)["title"] == "Opener"
    assert tl.song_at(400)["title"] == "Song 1" and tl.song_at(400 + 120)["title"] == "Song 1"
    assert tl.next_song(10)["title"] == "Song 1" and tl.next_song(400 + 119)["title"] == "Song 1"
    assert tl.length == 120
