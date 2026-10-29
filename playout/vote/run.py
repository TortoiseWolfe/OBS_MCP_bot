#!/usr/bin/env python3
"""Band Wagon fan-vote stream: full takes, one after another, to Twitch; chat votes !up / !down on the take playing.

One ffmpeg encodes the whole show. Its sound arrives on a continuous pipe (bwvote/pipe.py); as each song starts the player
picks the next take from the catalog (bwvote/catalog.py, bwvote/picker.py): no take twice until all have played, liked ones
earlier, new ones soon, new takes picked up as they land. No restart is needed for any of it; the only relaunch is ffmpeg
ending on its own.

usage:
  run.py live [--bandwidthtest] [--seconds N]   push to the channel (key read from the OBS profile, never shown)
  run.py local --out FILE --seconds N           same picture and sound into a local file, for a look
  run.py report                                 print the hourly tally line from the saved votes
  run.py stop                                   ask a running stream to stop
  run.py purge ID [--reason TEXT]               move a take aside (file kept in _purged); the stream leaves it out within a song or two
  run.py purge --restore ID                     bring it back
  run.py bottom                                 list the takes voted to the bottom
  run.py control                                the purge control page (separate process; answers only cfg["control"]["allow"])
Anything you type in chat other than !up / !down is ignored and never stored or shown.
"""
import argparse
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from bwvote import background, catalog, control, covers, ingest, meter, overlay, picker, pipe, playlist, purge, slideshow, viewers
from bwvote.tally import Tally, append_jsonl, load_state, parse_command, write_json

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # playout/: the shared chat reader and key redaction
import chat_tally  # noqa: E402
STATE = Path(os.environ.get("BWVOTE_STATE") or HERE / "state")  # another folder lets a test encode run beside the live stream
FPS = 5              # picture frames per second (build_cmd); the picture clock counts these
VOTE_LAG = 6.0       # seconds: what a viewer sees is about this far behind the encoder


def build_cmd(bg, out_dir, font, target, fmt, seconds=None):
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
           "-re", "-f", "image2", "-loop", "1", "-framerate", str(FPS), "-i", str(bg),  # -f image2: re-read every frame, so a new bg.png shows at once
           "-re", "-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "pipe:0",  # the audio pipe (bwvote/pipe.py)
           "-vf", vf, "-r", str(FPS),
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage,zerolatency", "-b:v", "1500k", "-maxrate", "1500k", "-bufsize", "3000k",
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
        self.timeline, self.feeder = None, None
        self.picker = picker.Picker(STATE / "picker.json")
        self.pos, self.pos_at = 0.0, time.time()
        self.frames, self.frames_at = 0, time.time()
        self.proc, self.started_at = None, 0.0
        self.opened = False
        self.last_play = None
        self.cover_now = None
        self.cover_idx = None
        self.slide_now = None

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

    def picture_position(self):
        """Where the encoder has got to in the picture (frames written / frame rate): the title and cover follow this, so they change on the
        frame that goes with the first sound of a take. The sound's own clock (position) is the lag-corrected one that votes use."""
        with self.lock:
            return self.frames / FPS + min(time.time() - self.frames_at, 1.0 / FPS)

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
    def choose(self):
        """The next take, drawn from the catalog as it stands now (new takes included)."""
        songs = catalog.load(self.cfg)
        self.all_songs = songs
        queued = picker.take_queued(STATE / "queue.json", songs)  # the show's running order: ids in queue.json play first, in order
        if queued:
            self.picker.note(queued)
            return queued
        return self.picker.pick(songs, self.tally)

    def launch(self):
        STATE.mkdir(exist_ok=True)
        self.all_songs = catalog.load(self.cfg)
        first = None
        if not self.opened:  # the opener plays once, at the first start only (a restart goes straight to the draw)
            first = playlist.opener_source(self.cfg)
            if first and first["path"].exists():
                self.picker.note(first)
            else:
                first = None
        self.opened = True
        self.timeline = pipe.LiveTimeline()
        self.last_play = None
        self.cover_idx = None
        self.slide_now = None
        cmd = build_cmd(STATE / "bg.png", STATE, self.cfg["font"], self.target, self.fmt, self.seconds)
        with self.lock:
            self.pos, self.pos_at = 0.0, time.time()
            self.frames, self.frames_at = 0, time.time()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.proc.stdout = io.TextIOWrapper(self.proc.stdout)  # stdin stays binary: it carries the sound
        self.proc.stderr = io.TextIOWrapper(self.proc.stderr, errors="replace")
        self.started_at = time.time()
        if self.feeder:
            self.feeder.stop.set()
        self.feeder = pipe.Feeder(self.proc.stdin, self.timeline, self.choose, first, log=log)
        self.feeder.start()
        if not self.feeder.started.wait(30):
            log("the first take did not start within 30 s")
        else:
            overlay.render(STATE, self.timeline.song_at(0), self.timeline.next_song(0), self.tally, self.all_songs, self.announce())
            self.show_cover(self.timeline.song_at(0))
        log(f"ffmpeg started: {len(self.all_songs)} takes in the catalog, next take chosen as each song starts")
        threading.Thread(target=self.read_progress, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self.read_errors, args=(self.proc,), daemon=True).start()

    # --- the encoder's own numbers ---------------------------------------
    def read_progress(self, proc):
        last = time.time()
        window = meter.Window()
        for line in proc.stdout:
            if line.startswith("speed=") and time.time() - last > 60:
                # ffmpeg's own figure averages everything since it started; the last-minute figure comes from the output position
                # and the clock time at which it was read, one mark a minute apart
                with self.lock:
                    pos, pos_at = self.pos, self.pos_at
                got = window.speed(pos, pos_at) if pos_at else None
                last = time.time()
                log(f"ffmpeg {line.strip()} since start; " + (f"{got:.3f}x over the last minute" if got is not None else "no last-minute figure yet"))
            if line.startswith("frame="):
                try:
                    n = int(line.split("=")[1])
                except ValueError:
                    continue
                with self.lock:
                    self.frames, self.frames_at = n, time.time()
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
            write_json(Path(self.cfg["export_to"]).expanduser(), self.tally.export(self.all_songs, purge.load(self.cfg)))

    def run(self):
        if self.cfg.get("channel"):  # a test encode into a file sets no channel and reads no chat
            threading.Thread(target=chat_tally.read_chat, args=(self.cfg["channel"], self.on_chat, self.stop), daemon=True).start()
            threading.Thread(target=viewers.run, args=(self.cfg["channel"], STATE / "viewers.jsonl", self.stop), daemon=True).start()
        self.launch()
        last_save = time.time()
        while not self.stop.is_set():
            time.sleep(0.25)
            rc = self.proc.poll()
            if rc is not None:
                if self.seconds and rc == 0:
                    break
                log(f"ffmpeg ended rc={rc}; restarting in 5 s")
                time.sleep(5)
                self.launch()
                continue
            if not self.timeline:
                continue
            p = self.position()
            pv = self.picture_position()
            slide = slideshow.current(self.cfg.get("slideshow"), song=self.timeline.song_at(pv))
            if slide:  # a show's slideshow window: the whole picture is the image, no vote words over it; votes and plays go on as usual
                if slide != self.slide_now:
                    try:
                        slideshow.build(slide, STATE / "bg.png")
                        slideshow.blank_text(STATE)
                        self.slide_now = slide
                    except Exception as e:  # a bad picture must never stop the stream
                        log(f"slide {slide.name} not shown: {e}")
                        self.slide_now = slide
            else:
                if self.slide_now:  # the window ended: the song's cover and the words come back
                    self.slide_now = None
                    self.cover_now = self.cover_idx = None
                overlay.render(STATE, self.timeline.song_at(pv), self.timeline.next_song(pv), self.tally, self.all_songs, self.announce())
            now = time.time()
            i, into = self.timeline.at(p)
            if i != self.last_play:
                self.last_play = i
                self.log_play(now - into, self.timeline.songs[i])
            iv = self.timeline.at(pv)[0]
            if iv != self.cover_idx and not self.slide_now:
                self.cover_idx = iv
                self.show_cover(self.timeline.songs[iv])
            if now - last_save > 10:
                self.save(); last_save = now
        self.halt_ffmpeg(); self.save()


def log(msg):
    print(f"{time.strftime('%-I:%M:%S %p')} {msg}", flush=True)


def side_mode(a, cfg):
    """purge, bottom and control: they read the tally and the catalog and write only purged.json (and the files they move)."""
    if a.mode == "control":
        return control.serve(cfg, STATE)
    songs = catalog.load(cfg)
    if a.mode == "bottom":
        for s in Tally(load_state(STATE / "tally.json")).bottom(songs):
            print(s["id"], s["title"])
        return
    if not a.target:
        sys.exit("purge needs a take id")
    try:
        if a.restore:
            purge.restore(cfg, a.target)
            print(f"restored {a.target}")
        else:
            song = next((s for s in songs if s["id"] == a.target), None)
            if not song:
                sys.exit(f"no such take on the air list: {a.target}")
            rec = purge.purge(cfg, song, a.reason)
            print(f"moved aside to {rec['moved_to']}")
    except (ValueError, OSError) as e:
        sys.exit(str(e))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["live", "local", "report", "stop", "purge", "bottom", "control"])
    ap.add_argument("target", nargs="?", help="take id, for purge")
    ap.add_argument("--restore", action="store_true", help="with purge: bring the take back")
    ap.add_argument("--reason", default="", help="with purge: why")
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
    cfg["purged_file"] = STATE / "purged.json"
    if a.mode in ("purge", "bottom", "control"):
        return side_mode(a, cfg)
    if a.mode == "report":
        print(Tally(load_state(STATE / "tally.json")).report_line(catalog.load(cfg)))
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
