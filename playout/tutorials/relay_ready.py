#!/usr/bin/env python3
"""Waits until the local relay really answers an RTMP handshake (the first step of an RTMP connection), then exits 0.

Why not just test that the port is open: Docker opens the port a moment before nginx inside the container is listening, accepts
the connection and then resets it. On 2 Nov the first go-live was ended by exactly that: the port test passed, the sender
connected in that gap, and it was reset ("Cannot read RTMP handshake response"). A handshake sends no stream, so nothing
is published anywhere and the relay forwards nothing.

usage: relay_ready.py PORT [SECONDS]      exit 0 = the relay answered; exit 1 = it did not within SECONDS (default 30)
"""
import os
import socket
import sys
import time

HANDSHAKE_REPLY = 1 + 1536 + 1536    # S0 + S1 + S2


def handshake_ok(host, port, timeout=3.0):
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(b"\x03" + os.urandom(1536))        # C0 + C1 (random bytes)
            got = b""
            while len(got) < HANDSHAKE_REPLY:
                chunk = s.recv(4096)
                if not chunk:
                    return False
                got += chunk
            return got[:1] == b"\x03"
    except OSError:
        return False


def wait_ready(host, port, seconds=30.0, pause=0.25, ok=handshake_ok):
    end = time.time() + seconds
    while True:
        if ok(host, port):
            return True
        if time.time() >= end:
            return False
        time.sleep(pause)


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    port = int(a[0])
    return 0 if wait_ready("127.0.0.1", port, float(a[1]) if len(a) > 1 else 30.0) else 1


if __name__ == "__main__":
    sys.exit(main())
