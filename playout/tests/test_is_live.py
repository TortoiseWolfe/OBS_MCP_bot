"""is_live.sh asks the API first (through a stubbed helper here) and falls back to the preview image (a local server here); no real network."""
import http.server
import os
import subprocess
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "is_live.sh"


def helper(tmp_path, body):
    p = tmp_path / "twitch_user.py"
    p.write_text(body)
    return p


def preview(status):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()

        def log_message(self, *a):
            pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/x.jpg"


def run(helper_path, url, channel="scripthammer"):
    env = {**os.environ, "TWITCH_HELPER": str(helper_path), "IS_LIVE_PREVIEW_URL": url}
    r = subprocess.run(["bash", str(SCRIPT), channel], env=env, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr


LIVE = "def helix(m, p, q):\n    assert (m, p, q) == ('GET', '/streams', {'user_login': 'scripthammer'})\n    return 200, {'data': [{'type': 'live'}]}\n"
OFF = "def helix(m, p, q):\n    return 200, {'data': []}\n"


def test_api_answer_wins_over_a_stale_preview(tmp_path):
    srv, url = preview(404)                                    # the preview still shows the offline placeholder
    try:
        assert run(helper(tmp_path, LIVE), url)[:2] == (0, "live (api)")
        assert run(helper(tmp_path, OFF), url)[:2] == (1, "offline (api)")
    finally:
        srv.shutdown()


def test_falls_back_to_the_preview_when_the_helper_is_missing_or_fails(tmp_path):
    srv, url = preview(200)
    try:
        assert run(tmp_path / "nope.py", url)[:2] == (0, "live (preview)")                       # no helper
        bad = helper(tmp_path, "import sys\ndef helix(m, p, q):\n    print('secret-token'); sys.exit(1)\n")
        rc, out, err = run(bad, url)
        assert (rc, out) == (0, "live (preview)") and "secret-token" not in out + err         # failed refresh: fall back, say nothing
        assert run(helper(tmp_path, "def helix(m, p, q):\n    return 401, {}\n"), url)[:2] == (0, "live (preview)")
        assert run(helper(tmp_path, "raise RuntimeError('x')\n"), url)[:2] == (0, "live (preview)")
    finally:
        srv.shutdown()
    srv, url = preview(404)
    try:
        assert run(tmp_path / "nope.py", url)[:2] == (1, "offline (preview)")
    finally:
        srv.shutdown()
    srv, url = preview(500)
    try:
        assert run(tmp_path / "nope.py", url)[0] == 2
    finally:
        srv.shutdown()
