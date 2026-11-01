#!/usr/bin/env python3
"""Says match or no-match for the Twitch stream key in every log file; never prints the key.

usage: keycheck.py KEYFILE PATH [PATH ...]      (PATH = file or folder; folders are walked)
  python3 keycheck.py ~/.config/afa/secrets/twitch-scripthammer.key ~/band-wagon-tower/replay ~/.claude/state/lanes/2026-10-29-bandwagon-replay
Two tests per file: the key's bytes anywhere in the file, and a sha256 compare of every token that follows
"twitch.tv/app/" with the key's sha256. Output: one line per file with a hit ("MATCH <file> <count>"), then a summary.
Skips media and image files. Exit 0 = no file holds the key, 1 = at least one does.
"""
import hashlib
import os
import re
import sys

SKIP = {".mp4", ".mp3", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".wav", ".m4a", ".mkv", ".flv", ".pyc"}
TOKEN = re.compile(rb"twitch\.tv/app/([^\s\"'<>&]+)")


def files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for d, _, fs in os.walk(p):
                for f in fs:
                    fp = os.path.join(d, f)
                    if os.path.isfile(fp) and not os.path.islink(fp) and os.path.splitext(f)[1].lower() not in SKIP:
                        yield fp


def check(path, key, digest):
    try:
        data = open(path, "rb").read()
    except OSError:
        return None
    n = data.count(key)
    h = sum(1 for m in TOKEN.finditer(data) if hashlib.sha256(m.group(1)).hexdigest() == digest)
    return max(n, h)


def main():
    key = b"".join(open(sys.argv[1], "rb").read().split())
    digest = hashlib.sha256(key).hexdigest()
    seen = hits = unread = 0
    for f in files(sys.argv[2:]):
        r = check(f, key, digest)
        seen += 1
        if r is None:
            unread += 1
        elif r:
            hits += 1
            print(f"MATCH {f} {r}")
    print(f"checked {seen} files, {hits} hold the key, {unread} unreadable: {'no-match' if not hits else 'MATCH'}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
