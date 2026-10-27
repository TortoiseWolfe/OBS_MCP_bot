"""Offline tests for the playout scripts (no network, no stream key)."""
import json
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import chat_tally
import push


def test_redact_hides_url_and_key():
    out = push.redact("Output #0, flv, to 'rtmp://live.twitch.tv/app/live_123_abc?bandwidthtest=true'", "live_123_abc")
    assert "live_123" not in out and "twitch.tv" not in out
    assert push.redact("error live_123_abc broke", "live_123_abc") == "error <key> broke"


def test_real_push_refused_before_show():
    et = ZoneInfo("America/New_York")
    assert not push.real_push_allowed(datetime(2026, 10, 28, 12, 0, tzinfo=et))
    assert not push.real_push_allowed(datetime(2026, 10, 29, 17, 56, tzinfo=et))
    assert push.real_push_allowed(datetime(2026, 10, 29, 17, 58, tzinfo=et))


def test_push_command_shape():
    cmd = push.build_cmd("x.mp4", 5520, "rtmp://h/app/k")
    assert cmd[cmd.index("-stream_loop") + 1] == "-1" and "-re" in cmd
    assert cmd[cmd.index("-c") + 1] == "copy" and cmd[cmd.index("-t") + 1] == "5520"


def test_set_lengths_match_slots():
    for name, mins, start in (("set1", 92, "17:58"), ("set2", 122, "19:58")):
        c = json.load(open(HERE / "sets" / f"{name}.json"))
        assert c["live_minutes"] == mins and c["live_start"].endswith(start)
        h, m = map(int, start.split(":")); end = h * 60 + m + mins
        assert end in (19 * 60 + 30, 22 * 60)  # 7:30 PM and 10:00 PM
        kinds = [i for i in c["items"]]
        files = [i.get("file") for i in kinds]
        assert files.index("bw-duet-1.mp3") < files.index("bw-duet-2.mp3")
        assert kinds[files.index("bw-duet-2.mp3") + 1]["kind"] == "card"


def test_parse_and_tally():
    assert chat_tally.parse_privmsg(":Ann!ann@ann.tmi.twitch.tv PRIVMSG #scripthammer :1") == ("ann", "1")
    assert chat_tally.parse_privmsg("@badges=;id=1 :bob!bob@bob.tmi.twitch.tv PRIVMSG #scripthammer :2 ") == ("bob", "2")
    assert chat_tally.parse_privmsg("PING :tmi.twitch.tv") is None
    t = chat_tally.Tally()
    for u, x in (("a", "1"), ("b", "2"), ("a", "2"), ("c", "hello"), ("d", "12"), ("e", "1")):
        t.feed(u, x)
    assert t.counts() == {"1": 1, "2": 2}  # a changed to 2; "hello" and "12" ignored


def test_tally_against_fake_irc(tmp_path):
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); port = srv.getsockname()[1]
    seen = {}

    def serve():
        c, _ = srv.accept(); seen["login"] = c.recv(4096).decode()
        c.sendall(b"PING :tmi.twitch.tv\r\n")
        for u, x in (("a", "1"), ("b", "1"), ("c", "2")):
            c.sendall(f":{u}!{u}@{u}.tmi.twitch.tv PRIVMSG #scripthammer :{x}\r\n".encode())
        time.sleep(3); seen["pong"] = c.recv(4096).decode(); c.close()

    th = threading.Thread(target=serve); th.start()
    out = tmp_path / "t.json"
    chat_tally.run(out, 3, "scripthammer", "127.0.0.1", port, False)
    th.join()
    d = json.loads(out.read_text())
    assert (d["take1"], d["take2"], d["leader"]) == (2, 1, "1")
    assert "NICK justinfan" in seen["login"] and "oauth" not in seen["login"].lower()
    assert "PONG" in seen["pong"]


def test_is_live_script_usage():
    r = subprocess.run([str(HERE / "is_live.sh")], capture_output=True, text=True)
    assert r.returncode != 0
