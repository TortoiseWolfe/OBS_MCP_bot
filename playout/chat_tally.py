#!/usr/bin/env python3
"""Read-only anonymous Twitch chat reader: counts "1" and "2" votes in #scripthammer.

usage: chat_tally.py <outfile.json> [--seconds N] [--channel scripthammer] [--host H --port P --plain]
Logs in as justinfan<random> (no token, cannot post). One vote per viewer: their latest "1" or "2" counts.
Writes the tally file every 5 s and at the end.
"""
import argparse
import json
import random
import socket
import ssl
import threading
import time
from pathlib import Path


def parse_privmsg(line):
    """':user!user@user.tmi.twitch.tv PRIVMSG #chan :text' -> (user, text) or None."""
    if " PRIVMSG " not in line:
        return None
    if line.startswith("@"):
        line = line.split(" ", 1)[1]
    prefix, _, rest = line.partition(" PRIVMSG ")
    user = prefix.lstrip(":").split("!", 1)[0]
    _, _, text = rest.partition(" :")
    return user.lower(), text.strip()


class Tally:
    def __init__(self):
        self.votes = {}

    def feed(self, user, text):
        if text in ("1", "2"):
            self.votes[user] = text

    def counts(self):
        return {"1": sum(v == "1" for v in self.votes.values()), "2": sum(v == "2" for v in self.votes.values())}

    def write(self, path, channel, started):
        c = self.counts()
        out = {"channel": channel, "started": started, "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
               "take1": c["1"], "take2": c["2"], "voters": len(self.votes),
               "leader": "1" if c["1"] > c["2"] else "2" if c["2"] > c["1"] else "tie"}
        tmp = Path(str(path) + ".tmp"); tmp.write_text(json.dumps(out, indent=2)); tmp.replace(path)


def read_chat(channel, on_message, stop, host="irc.chat.twitch.tv", port=6697, tls=True, on_tick=None):
    """Read-only chat loop shared by the take tally and the vote stream.

    Blocks until `stop` (a threading.Event) is set and reconnects after a drop; calls on_message(user, text) per
    chat line and on_tick() after every read.
    """
    while not stop.is_set():
        try:
            s = socket.create_connection((host, port), timeout=30)
            if tls:
                s = ssl.create_default_context().wrap_socket(s, server_hostname=host)
            s.settimeout(5)
            s.sendall(f"PASS SCHMOOPIIE\r\nNICK justinfan{random.randint(10000, 99999)}\r\nJOIN #{channel}\r\n".encode())
            buf = b""
            while not stop.is_set():
                try:
                    data = s.recv(4096)
                except (TimeoutError, socket.timeout):
                    data = None
                if data == b"":
                    break  # server closed: reconnect
                if data:
                    buf += data
                    while b"\r\n" in buf:
                        raw, buf = buf.split(b"\r\n", 1)
                        line = raw.decode("utf-8", "replace")
                        if line.startswith("PING"):
                            s.sendall(b"PONG :tmi.twitch.tv\r\n")
                        m = parse_privmsg(line)
                        if m:
                            on_message(*m)
                if on_tick:
                    on_tick()
            s.close()
        except OSError:
            stop.wait(5)


def run(outfile, seconds, channel, host, port, tls):
    t = Tally(); started = time.strftime("%Y-%m-%d %H:%M:%S")
    stop = threading.Event()
    timer = threading.Timer(seconds, stop.set); timer.daemon = True; timer.start()
    next_write = [0.0]

    def tick():
        if time.time() >= next_write[0]:
            t.write(outfile, channel, started); next_write[0] = time.time() + 5

    read_chat(channel, t.feed, stop, host, port, tls, on_tick=tick)
    t.write(outfile, channel, started)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("outfile"); ap.add_argument("--seconds", type=int, default=7200)
    ap.add_argument("--channel", default="scripthammer"); ap.add_argument("--host", default="irc.chat.twitch.tv")
    ap.add_argument("--port", type=int, default=6697); ap.add_argument("--plain", action="store_true")
    a = ap.parse_args()
    run(a.outfile, a.seconds, a.channel, a.host, a.port, not a.plain)
