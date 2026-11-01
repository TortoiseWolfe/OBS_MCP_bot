"""air.sh keeps the stream key out of its log. Uses a fake key and a dead local port: nothing goes to Twitch.

Control: the old way (ffmpeg's own log, no filter) does put the fake key in the log, so the check can see a leak.
"""
import os
import subprocess
import tempfile
import time
from pathlib import Path

AIR = Path(__file__).resolve().parent.parent / "air"
FAKE = "live_000000000_FAKEFAKEFAKEFAKEFAKEFAKEFAKE"


def _film(root, tag):
    d = Path(root) / "replay" / tag
    d.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10", "-f", "lavfi", "-i", "sine", "-t", "2",
                    "-c:v", "libx264", "-c:a", "aac", str(d / "film.mp4")], check=True)


def _keycheck(key, *paths):
    return subprocess.run(["python3", str(AIR / "keycheck.py"), str(key), *map(str, paths)], capture_output=True, text=True)


def test_air_log_has_no_key_and_old_style_log_does():
    with tempfile.TemporaryDirectory() as root:
        key = Path(root) / "fake.key"
        key.write_text(FAKE + "\n")
        _film(root, "film-t")
        env = dict(os.environ, AIR_ROOT=root, AIR_KEYFILE=str(key), AIR_RTMP_BASE="rtmp://127.0.0.1:9/app")
        subprocess.run(["bash", str(AIR / "air.sh"), "film-t"], env=env, check=True, capture_output=True, text=True)
        log = Path(root) / "replay" / "air-film-t.log"
        for _ in range(100):
            time.sleep(0.1)
            pid = (Path(root) / "replay" / "air.pid").read_text().strip()
            if not Path(f"/proc/{pid}").exists():
                break
        time.sleep(0.5)
        assert log.exists() and log.stat().st_size > 0, "the log should hold ffmpeg's connection error"
        r = _keycheck(key, log)
        assert r.returncode == 0 and "no-match" in r.stdout, r.stdout
        old = Path(root) / "old.log"
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-re", "-i", str(Path(root) / "replay" / "film-t" / "film.mp4"), "-c", "copy", "-f", "flv",
                        f"rtmp://127.0.0.1:9/app/{FAKE}"], stdout=old.open("w"), stderr=subprocess.STDOUT)
        assert _keycheck(key, old).returncode == 1, "the control log should show the leak"


def test_split_key_across_chunks_is_still_replaced():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rs", AIR / "redact-stream.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    key = FAKE.encode()
    for cut in (1, 7, len(key) - 1):
        r, w = os.pipe()
        out_r, out_w = os.pipe()
        data = b"to rtmp://x/app/" + key + b" failed\r"
        os.write(w, data[:16 + cut])
        t = __import__("threading").Thread(target=m.run, args=(r, out_w, key))
        t.start()
        time.sleep(0.05)
        os.write(w, data[16 + cut:])
        os.close(w)
        t.join()
        os.close(out_w)
        got = os.read(out_r, 65536)
        assert key not in got and b"[stream-key]" in got and got.endswith(b" failed\r"), got
