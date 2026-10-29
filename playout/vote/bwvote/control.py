"""The purge control page: every take ranked by net vote, the bottom ones flagged, Purge and Restore buttons.

A separate process from the stream (run.py control). It reads state/tally.json and the catalog, and writes only purged.json
(bwvote/purge.py) and the files it moves. It never touches the stream or OBS. It answers only the one client address set as
cfg["control"]["allow"] (the owner's PC on the home network): any other address is refused before a header, path or body is read.
On top of that the Host header must be the page's own address and a POST's Origin must match it.

Behind the tower's Windows port forward (control-forward.ps1) every request reaches this process from the forwarder, so the
source address seen here is loopback, not the owner's PC. Then cfg["control"] sets "bind": "127.0.0.1", "forwarders": ["127.0.0.1"]
and "hosts": ["192.168.1.3:8780", "127.0.0.1:8780"]; the Windows firewall rule that admits only the owner's PC's address is the
allowlist on that path, and this process is reachable from this machine only.
"""
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import catalog, purge
from .tally import Tally, load_state

LOCK = threading.Lock()  # one purge or restore at a time

PAGE = """<!doctype html><meta charset="utf-8"><title>Band Wagon takes</title>
<style>body{{font:16px system-ui;margin:1.5rem;max-width:56rem}}table{{border-collapse:collapse;width:100%}}
td,th{{padding:.4rem .6rem;border-bottom:1px solid #ccc;text-align:left}}.flag{{background:#fde8e8}}
button{{min-height:44px;min-width:44px;font-size:1rem}}#msg{{min-height:1.5rem;font-weight:bold}}</style>
<h1>Band Wagon takes</h1><p>{voters} voters. Ranked by net votes (likes minus dislikes), then fewest dislikes. Purge moves a file aside; it is never deleted.</p>
<div id="msg" role="status"></div>
<table><tr><th>Take</th><th>Up</th><th>Down</th><th>Net</th><th></th></tr>{rows}</table>
<details><summary>Moved aside ({n_aside})</summary><table>{aside}</table></details>
<script>
async function act(path, id, reason) {{
  const r = await fetch(path, {{method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({{id, reason}})}});
  const j = await r.json();
  if (r.ok) location.reload(); else document.getElementById("msg").textContent = j.error || "failed";
}}
document.addEventListener("click", e => {{
  const b = e.target.closest("button[data-act]"); if (!b) return;
  if (b.dataset.act === "purge") {{
    const why = b.dataset.flag ? "voted to the bottom" : "owner's choice";
    if (confirm("Move '" + b.dataset.title + "' aside? The file is kept in _purged and can be restored.")) act("/purge", b.dataset.id, why);
  }} else act("/restore", b.dataset.id, "");
}});
</script>"""


def _button(act, sid, title, flag=False):
    label = "Purge" if act == "purge" else "Restore"
    return (f'<button data-act="{act}" data-id="{html.escape(sid, quote=True)}" data-title="{html.escape(title, quote=True)}"'
            f'{" data-flag=1" if flag else ""}>{label}</button>')


def render(cfg, tally, songs=None):
    songs = catalog.load(cfg) if songs is None else songs
    bottom = {s["id"] for s in tally.bottom(songs)}
    rows = []
    for s, up, down in tally.ranked_all(songs):
        flag = s["id"] in bottom
        title = html.escape(s["title"]) + (" <strong>(bottom)</strong>" if flag else "")
        rows.append(f'<tr{" class=flag" if flag else ""}><td>{title}</td><td>{up}</td><td>{down}</td><td>{up - down}</td>'
                    f'<td>{_button("purge", s["id"], s["title"], flag)}</td></tr>')
    aside = []
    for sid, rec in purge.load(cfg).items():
        up, down = tally.counts(sid)
        aside.append(f'<tr><td>{html.escape(rec.get("title", sid))}</td><td>{up}</td><td>{down}</td>'
                     f'<td>{html.escape(rec.get("reason", ""))}</td><td>{_button("restore", sid, rec.get("title", sid))}</td></tr>')
    return PAGE.format(voters=tally.viewers(), rows="".join(rows), aside="".join(aside), n_aside=len(aside))


def make_handler(cfg, state_dir, allow, hosts):
    state_dir = Path(state_dir)
    allow = {allow} if isinstance(allow, str) else set(allow)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj), "application/json")

        def _allowed(self):
            if self.client_address[0] not in allow:  # first thing: nothing else is read from anyone else
                self._json(403, {"error": "not allowed"})
                return False
            if self.headers.get("Host", "") not in hosts:
                self._json(403, {"error": "bad host"})
                return False
            return True

        def do_GET(self):
            if not self._allowed():
                return
            if self.path.split("?")[0] != "/":
                return self._json(404, {"error": "not found"})
            self._send(200, render(cfg, Tally(load_state(state_dir / "tally.json"))))

        def do_POST(self):
            if not self._allowed():
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin.replace("http://", "", 1) not in hosts:
                return self._json(403, {"error": "bad origin"})
            if self.path not in ("/purge", "/restore"):
                return self._json(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n <= 0 or n > 4096:
                    raise ValueError
                req = json.loads(self.rfile.read(n))
                sid, reason = str(req["id"]), str(req.get("reason", ""))
            except (ValueError, KeyError, TypeError):
                return self._json(400, {"error": "bad request"})
            try:
                with LOCK:
                    if self.path == "/purge":
                        song = next((s for s in catalog.load(cfg) if s["id"] == sid), None)
                        if not song:
                            return self._json(404, {"error": "no such take on the air list"})
                        purge.purge(cfg, song, reason)
                    else:
                        purge.restore(cfg, sid)
            except (ValueError, OSError) as e:
                return self._json(409, {"error": str(e)})
            self._json(200, {"ok": True})

    return Handler


def serve(cfg, state_dir):
    c = cfg.get("control") or {}
    allow, bind, port = c.get("allow"), c.get("bind"), int(c.get("port", 8780))
    if not (allow and bind):
        raise SystemExit('set "control": {"allow": <owner PC address>, "bind": <this machine\'s home-network address>} in playlist.json')
    hosts = set(c.get("hosts") or [f"{bind}:{port}"])
    clients = {allow} | set(c.get("forwarders") or [])
    server = ThreadingHTTPServer((bind, port), make_handler(cfg, state_dir, clients, hosts))
    print(f"control page bound to {bind}:{port}, answers {sorted(clients)}, hosts {sorted(hosts)}", flush=True)
    server.serve_forever()
