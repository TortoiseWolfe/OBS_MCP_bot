#!/usr/bin/env python3
"""Band Wagon fan-vote stream: loops the full songs (the practice jams too) to Twitch; chat votes !up / !down on the song playing.

One ffmpeg runs the whole list start to finish. Votes are saved and shown on screen but change the play order only at the
next start of this program (the scheduled stop and restart); the only relaunch is ffmpeg ending on its own.

usage:
  run.py live [--bandwidthtest] [--seconds N]   push to the channel (key read from the OBS profile, never shown)
  run.py local --out FILE --seconds N           same picture and sound into a local file, for a look
  run.py report                                 print the hourly tally line from the saved votes
  run.py stop                                   ask a running stream to stop
Anything you type in chat other than !up / !down is ignored and never stored or shown.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from bwvote import background, covers, ingest, overlay, playlist, viewers, weights
from bwvote.tally import Tally, append_jsonl, load_state, parse_command, write_json

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # playout/: the shared chat reader and key redaction
import chat_tally  # noqa: E402
STATE = HERE / "state"
VOTE_LAG = 6.0       # seconds: what a viewer sees is about this far behind the encoder


def build_cmd(bg, list_file, out_dir, font, target, fmt, seconds=None):
    def dt(name, x, y, size, color, extra=""):
        return (f"drawtext=fontfile={font}:textfile={out_dir}/{name}.txt:reload=1:expansion=none:"
                f"x={x}:y={y}:fontsize={size}:fontcolor={color}{extra}")
    vf = ",".join([dt("title", 690, 92, 44, "white", ":line_spacing=6"),
                   dt("tally", 690, 300, 62, "0xFFC440"),
                   dt("note", 690, 366, 34, "0xFFC440"),
                   dt("top", 690, 532, 23, "white", ":line_spacing=4"),
                   dt("next", 690, 626, 22, "0xBEE6FF"),
                   "format=yuv420p"])
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-progress", "pipe:1", "-nostats",
           "-re", "-f", "image2", "-loop", "1", "-framerate", "5", "-i", str(bg),  # -f image2: re-read every frame, so a new bg.png shows at once
           "-re", "-f", "concat", "-safe", "0", "-i", str(list_file),
           "-vf", vf, "-r", "5",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k",
           "-g", "10", "-keyint_min", "10", "-sc_threshold", "0",  # still picture: 5 fps, a keyframe every 2 s (Twitch needs one)
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
    if seconds:
        cmd += ["-t", str(seconds)]
    return cmd + ["-f", fmt, target]


class Stream:
    def __init__(self, cfg, target, key, fmt, seconds):
        self.cfg, self.target, self.key, self.fmt, self.seconds = cfg, target, key, fmt, seconds
        self.tally = Tally(load_state(STATE / "tally.json"))
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.all_songs = cfg["songs"]
        self.songs, self.timeline = [], None
        self.pos, self.pos_at = 0.0, time.time()
        self.proc, self.started_at = None, 0.0
        self.opened = False
        self.last_play = None
        self.cover_now = None

    def show_cover(self, song):
        """Put the song's own cover (beside Now Playing) into bg.png, which ffmpeg re-reads every frame."""
        cover = covers.cover_for(song, covers.load(self.cfg.get("song_covers", "")), self.cfg["cover"])
        if cover != self.cover_now:
            try:
                background.build(cover, self.cfg["font"], STATE / "bg.png")
                self.cover_now = cover
            except Exception as e:  # a bad picture must never stop the stream: keep the one on screen
                log(f"cover {cover.name} not shown: {e}")

    def announce(self):
        return overlay.active_announcement(self.cfg.get("announcements"))

    # --- what is playing -------------------------------------------------
    def position(self, lag=0.0):
        with self.lock:
            return max(0.0, self.pos + min(time.time() - self.pos_at, 2.0) - lag)

    def on_chat(self, user, text):
        v = parse_command(text)
        if not (v and self.timeline):
            return
        now = time.time()
        pos = self.position(VOTE_LAG)
        i, into = self.timeline.at(pos)
        song = self.timeline.songs[i]
        if song.get("opener"):
            return
        h = self.tally.vote(song["id"], user, v)
        # one clock for both logs: this machine's, read here and in the play log below
        append_jsonl(STATE / "votes.jsonl", {"epoch": round(now, 2), "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                                             "song": song["id"], "title": song["title"], "into_song_s": round(into, 1),
                                             "vote": v, "voter": h})

    def log_play(self, now, song, kind="start"):
        append_jsonl(STATE / "plays.jsonl", {"epoch": round(now, 2), "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                                             "song": song["id"], "title": song["title"], "event": kind})

    # --- ffmpeg ----------------------------------------------------------
    def launch(self):
        STATE.mkdir(exist_ok=True)
        chosen = playlist.full_songs(self.all_songs)
        playlist.with_durations(chosen)
        lead = None
        if not self.opened:  # the opener plays once, at the first start only (a restart goes straight to the loop)
            op = playlist.opener_source(self.cfg)
            if op and op["path"].exists():
                lead = playlist.with_durations([op])
        self.opened = True
        # the play order follows the votes as they stand now; it is fixed until the encoder next restarts
        after = self.timeline.song_at(self.position())["id"] if self.timeline and not lead else None
        seq = weights.sequence(chosen, self.tally, after_id=after)
        self.songs, self.timeline = chosen, playlist.Timeline(seq, lead)
        self.last_play = None
        (STATE / "list.txt").write_text(playlist.concat_list(seq, repeats=1, lead=lead))
        odd = ", ".join(f"{k.split('/')[-1][3:-4]} x{v:g}" for k, v in weights.weights(chosen, self.tally).items() if v != 1.0)
        log("weights: " + (odd or "all even"))
        overlay.render(STATE, self.timeline.song_at(0), self.timeline.next_song(0), self.tally, self.all_songs, self.announce())
        self.show_cover(self.timeline.song_at(0))
        cmd = build_cmd(STATE / "bg.png", STATE / "list.txt", STATE, self.cfg["font"], self.target, self.fmt, self.seconds)
        with self.lock:
            self.pos, self.pos_at = 0.0, time.time()
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.started_at = time.time()
        log(f"ffmpeg started: {len(chosen)} full songs, loop {self.timeline.length:.0f}s")
        threading.Thread(target=self.read_progress, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self.read_errors, args=(self.proc,), daemon=True).start()

    def read_progress(self, proc):
        t0 = last = time.time()
        mark_out = mark_el = 0.0
        for line in proc.stdout:
            if line.startswith("speed=") and time.time() - last > 60:
                # speed over the last minute, worked out from ffmpeg's own running figure (which averages in the start-up pause)
                now = time.time()
                try:
                    out, el = float(line.split("=")[1].strip().rstrip("x")) * (now - t0), now - t0
                except ValueError:
                    continue
                log(f"ffmpeg {line.strip()} since start; {(out - mark_out) / (el - mark_el):.3f}x over the last minute")
                last, mark_out, mark_el = now, out, el
            if line.startswith("out_time_us="):
                try:
                    us = int(line.split("=")[1])
                except ValueError:
                    continue
                with self.lock:
                    self.pos, self.pos_at = us / 1e6, time.time()

    def read_errors(self, proc):
        last = 0
        for line in proc.stderr:
            line = ingest.redact(line.strip(), self.key)
            if line and (("error" in line.lower() or "drop" in line.lower()) or time.time() - last > 600):
                last = time.time()
                log("ffmpeg: " + line[:200])

    def halt_ffmpeg(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    # --- main loop -------------------------------------------------------
    def save(self):
        write_json(STATE / "tally.json", self.tally.state())
        if self.cfg.get("export_to"):
            write_json(Path(self.cfg["export_to"]).expanduser(), self.tally.export(self.all_songs))

    def run(self):
        threading.Thread(target=chat_tally.read_chat, args=(self.cfg["channel"], self.on_chat, self.stop), daemon=True).start()
        threading.Thread(target=viewers.run, args=(self.cfg["channel"], STATE / "viewers.jsonl", self.stop), daemon=True).start()
        self.launch()
        last_save = time.time()
        while not self.stop.is_set():
            time.sleep(1)
            rc = self.proc.poll()
            if rc is not None:
                if self.seconds and rc == 0:
                    break
                log(f"ffmpeg ended rc={rc}; restarting in 5 s")
                time.sleep(5)
                self.launch()
                continue
            p = self.position()
            overlay.render(STATE, self.timeline.song_at(p), self.timeline.next_song(p), self.tally, self.all_songs, self.announce())
            now = time.time()
            i, into = self.timeline.at(p)
            if i != self.last_play:
                self.last_play = i
                self.show_cover(self.timeline.songs[i])
                self.log_play(now - into, self.timeline.songs[i])
            if now - last_save > 10:
                self.save(); last_save = now
        self.halt_ffmpeg(); self.save()


def log(msg):
    print(f"{time.strftime('%-I:%M:%S %p')} {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["live", "local", "report", "stop"])
    ap.add_argument("--bandwidthtest", action="store_true")
    ap.add_argument("--channel", help="channel to read chat from (default: playlist.json)")
    ap.add_argument("--key-file", help="file holding just the stream key (default: the OBS profile)")
    ap.add_argument("--seconds", type=int)
    ap.add_argument("--no-opener", action="store_true", help="skip the opening song (restarting a show already under way)")
    ap.add_argument("--out")
    ap.add_argument("--playlist", default=str(HERE / "playlist.json"))
    a = ap.parse_args()
    cfg = playlist.load(a.playlist)
    if a.channel:
        cfg["channel"] = a.channel
    STATE.mkdir(exist_ok=True)
    if a.mode == "report":
        print(Tally(load_state(STATE / "tally.json")).report_line(cfg["songs"]))
        return
    pidfile = STATE / "run.pid"
    if a.mode == "stop":
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        return
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), 0)
            sys.exit("already running (state/run.pid)")
        except (OSError, ValueError):
            pass
    pidfile.write_text(str(os.getpid()))
    background.build(cfg["cover"], cfg["font"], STATE / "bg.png")
    if a.mode == "live":
        target, key = ingest.load(a.bandwidthtest, a.key_file)
        fmt = "flv"
    else:
        target, key, fmt = a.out, "", "flv"
    cfg["font"] = str(Path(cfg["font"]).expanduser())
    if a.no_opener:
        cfg.pop("opener", None)
    s = Stream(cfg, target, key, fmt, a.seconds)
    signal.signal(signal.SIGTERM, lambda *_: s.stop.set())
    signal.signal(signal.SIGINT, lambda *_: s.stop.set())
    try:
        s.run()
    finally:
        pidfile.unlink(missing_ok=True)
        log("stopped")


if __name__ == "__main__":
    main()
