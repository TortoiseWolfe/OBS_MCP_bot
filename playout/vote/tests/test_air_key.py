"""air.sh keeps the stream key off every process command line, and the relay really forwards the stream.

Fake key and local ports only: nothing goes to Twitch. Needs Docker and ffmpeg. Prints/asserts counts, never the key.
  python3 -m pytest tests/test_air_key.py     (or call the test_ functions by hand)
"""
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

AIR = Path(__file__).resolve().parent.parent / "air"
FAKE = "live_000000000_FAKEFAKEFAKEFAKEFAKEFAKEFAKE"


def cmdline_matches(needle: bytes) -> int:
    """How many processes have the needle in their command line (reads /proc/*/cmdline; returns a count only)."""
    n = 0
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                if needle in (d / "cmdline").read_bytes():
                    n += 1
            except OSError:
                pass
    return n


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _film(root, tag, seconds):
    d = Path(root) / "replay" / tag
    d.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10", "-f", "lavfi", "-i", "sine",
                    "-t", str(seconds), "-c:v", "libx264", "-c:a", "aac", str(d / "film.mp4")], check=True)


def _env(root, key, base, port, proj):
    return dict(os.environ, AIR_ROOT=str(root), AIR_KEYFILE=str(key), AIR_RTMP_BASE=base, AIR_RELAY_PORT=str(port), AIR_RELAY_PROJECT=proj)


def _wait_gone(pidfile, limit=60):
    pid = Path(pidfile).read_text().strip()
    for _ in range(limit * 10):
        if not Path(f"/proc/{pid}").exists():
            return
        time.sleep(0.1)


def _down(proj):
    subprocess.run(["timeout", "120", "docker", "compose", "-p", proj, "-f", str(AIR / "relay" / "compose.yml"), "down"],
                   env=dict(os.environ, RELAY_CONF="/dev/null"), capture_output=True)


def test_key_is_on_no_command_line_while_a_test_stream_runs():
    proj = "bw-air-relay-test"
    with tempfile.TemporaryDirectory() as root:
        key = Path(root) / "fake.key"
        key.write_text(FAKE + "\n")
        _film(root, "film-t", 25)
        port = _free_port()
        env = _env(root, key, "rtmp://127.0.0.1:9/app", port, proj)  # port 9: nothing listens, so the relay's push to "Twitch" is refused
        try:
            r = subprocess.run(["bash", str(AIR / "air.sh"), "film-t"], env=env, capture_output=True, text=True, timeout=180)
            assert r.returncode == 0, r.stdout + r.stderr
            time.sleep(4)  # the stream is running now
            assert Path(f"/proc/{(Path(root) / 'replay' / 'air.pid').read_text().strip()}").exists(), "the test stream should still be running"
            with_key = cmdline_matches(FAKE.encode())
            conf = Path(root) / "replay" / "relay-run" / "nginx.conf"
            assert oct(conf.stat().st_mode & 0o777) == "0o600"
            assert FAKE in conf.read_text(), "the relay config should hold the address"
            inspect = subprocess.run(["docker", "inspect", f"{proj}-relay-1"], capture_output=True, text=True).stdout
            control = subprocess.Popen(["python3", "-c", "import time;time.sleep(30)", FAKE])  # a command line that does hold the key, so the scan is shown to see one
            time.sleep(0.3)
            seen_control = cmdline_matches(FAKE.encode())
            control.kill()
            control.wait()
            print(f"command lines holding the key while streaming: {with_key}; control: {seen_control}")
            assert with_key == 0
            assert seen_control >= 1
            assert FAKE not in inspect
            _wait_gone(Path(root) / "replay" / "air.pid")
            time.sleep(8)  # the watcher takes the relay down after ffmpeg ends
            names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
            assert f"{proj}-relay-1" not in names
            assert FAKE not in (Path(root) / "replay" / "air-film-t.log").read_text()
        finally:
            _down(proj)


def test_relay_forwards_the_stream():
    proj = "bw-air-relay-test2"
    with tempfile.TemporaryDirectory() as root:
        key = Path(root) / "fake.key"
        key.write_text(FAKE + "\n")
        _film(root, "film-t", 8)
        sink_port, port = _free_port(), _free_port()
        out = Path(root) / "sink.flv"
        sink = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-listen", "1", "-i", f"rtmp://0.0.0.0:{sink_port}/app/{FAKE}", "-c", "copy", "-y", str(out)],
                                stderr=subprocess.DEVNULL)
        time.sleep(1)
        env = _env(root, key, f"rtmp://host.docker.internal:{sink_port}/app", port, proj)
        try:
            r = subprocess.run(["bash", str(AIR / "air.sh"), "film-t"], env=env, capture_output=True, text=True, timeout=180)
            assert r.returncode == 0, r.stdout + r.stderr
            _wait_gone(Path(root) / "replay" / "air.pid")
            sink.wait(timeout=30)
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout or 0)
            print(f"sink received {dur:.1f} s of an 8 s film")
            assert 6 <= dur <= 9
        finally:
            sink.kill()
            _down(proj)
