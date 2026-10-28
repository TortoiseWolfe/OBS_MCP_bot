"""One encoder, fed by one continuous audio pipe. The next take is chosen as each song starts, never from a fixed list.

Each take is decoded by its own short ffmpeg to raw sound (48000 Hz, stereo, 16-bit) and written straight on to the
encoder's standard input, so the encoder never sees a song change and never restarts. The encoder's own clock
(`-re`) paces the pipe: a write blocks when the pipe is full. Every byte written is counted, so the start of each song
on the stream clock is known exactly.
"""
import subprocess
import threading
import time
from bisect import bisect_right

BYTES_PER_S = 48000 * 2 * 2
CHUNK = BYTES_PER_S // 10  # 0.1 s


def decode_cmd(path):
    return ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-vn", "-f", "s16le", "-ar", "48000", "-ac", "2", "-"]


class LiveTimeline:
    """Stream seconds -> (song index, seconds into it); songs are added as they start. Same questions as the old fixed list."""

    def __init__(self):
        self.songs, self.starts, self.upcoming = [], [], None
        self.lock = threading.Lock()

    def __bool__(self):
        return bool(self.songs)

    def begin(self, song, start):
        with self.lock:
            self.songs.append(song)
            self.starts.append(start)

    def drop_last(self):
        with self.lock:
            self.songs.pop(); self.starts.pop()

    def at(self, position):
        with self.lock:
            i = max(0, bisect_right(self.starts, position) - 1)
            return i, position - self.starts[i]

    def song_at(self, position):
        return self.songs[self.at(position)[0]]

    def next_song(self, position):
        i = self.at(position)[0]
        return self.songs[i + 1] if i + 1 < len(self.songs) else self.upcoming


class Feeder(threading.Thread):
    """Writes take after take into `sink` (the encoder's stdin). `choose()` gives the next take; `first` plays first if given."""

    def __init__(self, sink, timeline, choose, first=None, log=print, decoder=decode_cmd):
        super().__init__(daemon=True)
        self.sink, self.timeline, self.choose, self.first, self.log, self.decoder = sink, timeline, choose, first, log, decoder
        self.stop, self.started, self.sent = threading.Event(), threading.Event(), 0

    def run(self):
        cur = self.first or self.choose()
        failures = 0
        while not self.stop.is_set():
            start = self.sent / BYTES_PER_S
            self.timeline.begin(cur, start)
            nxt = None
            try:
                dec = subprocess.Popen(self.decoder(cur["path"]), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except OSError as e:
                self.log(f"decoder would not start: {e}")
                return
            n = 0
            try:
                while not self.stop.is_set():
                    chunk = dec.stdout.read(CHUNK)
                    if not chunk:
                        break
                    if nxt is None:  # the song is on its way: now choose what follows
                        nxt = self.choose()
                        self.timeline.upcoming = nxt
                        self.started.set()
                    self.sink.write(chunk)
                    self.sink.flush()
                    n += len(chunk)
                    self.sent += len(chunk)
            except (BrokenPipeError, ValueError, OSError):
                self.log("encoder pipe closed; feeder stops")
                return
            finally:
                dec.kill(); dec.wait()
            if self.stop.is_set():
                return
            if n < BYTES_PER_S:  # nothing or next to nothing came out: skip it, never spin
                self.log(f"skipped {cur['id']}: {n} bytes decoded")
                self.timeline.drop_last()
                self.sent -= n
                failures += 1
                if failures > 20:
                    self.log("20 takes in a row would not decode; feeder stops")
                    return
                time.sleep(0.5)
                cur = nxt or self.choose()
                continue
            failures = 0
            cur = nxt
