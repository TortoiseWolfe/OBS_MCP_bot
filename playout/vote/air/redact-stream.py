#!/usr/bin/env python3
"""Copies stdin to stdout and replaces the stream key (read from the key file named in argv[1]) with [stream-key].

usage: some-command 2> >(python3 redact-stream.py KEYFILE >> LOG)
Works on raw chunks so ffmpeg's carriage-return progress lines pass through at once; only a tail of the buffer that
could be the start of the key is held back until the next chunk. Never prints the key, even on an error.
"""
import os
import sys

MARK = b"[stream-key]"


def hold_len(buf, key):
    """Length of the longest end of buf that is also a start of key (that part may be a split key)."""
    for n in range(min(len(buf), len(key) - 1), 0, -1):
        if key.startswith(buf[-n:]):
            return n
    return 0


def run(src_fd, dst_fd, key):
    buf = b""
    while True:
        chunk = os.read(src_fd, 65536)
        if not chunk:
            break
        buf = (buf + chunk).replace(key, MARK)
        keep = hold_len(buf, key)
        out, buf = buf[:len(buf) - keep], buf[len(buf) - keep:]
        if out:
            os.write(dst_fd, out)
    if buf:
        os.write(dst_fd, buf.replace(key, MARK))


def main():
    try:
        key = b"".join(open(sys.argv[1], "rb").read().split())
    except OSError:
        key = b""
    if not key:
        sys.stderr.write("redact-stream: no key to redact; refusing to pass the stream through\n")
        sys.exit(2)
    run(0, 1, key)


if __name__ == "__main__":
    main()
