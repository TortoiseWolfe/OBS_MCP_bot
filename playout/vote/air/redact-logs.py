#!/usr/bin/env python3
"""Replaces the stream key with [stream-key] in place in every non-media file under the given folders.

usage: redact-logs.py KEYFILE FOLDER [FOLDER ...]
Prints only file names and counts, never the key. Keeps each file's mode and modified time.
Writes a temporary file beside the original and swaps it in; nothing is deleted.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keycheck import files  # noqa: E402

MARK = b"[stream-key]"


def main():
    key = b"".join(open(sys.argv[1], "rb").read().split())
    if not key:
        sys.exit("empty key file")
    total = n = 0
    for f in files(sys.argv[2:]):
        try:
            data = open(f, "rb").read()
        except OSError:
            continue
        c = data.count(key)
        if not c:
            continue
        st = os.stat(f)
        tmp = f + ".redact-tmp"
        with open(tmp, "wb") as w:
            w.write(data.replace(key, MARK))
        os.chmod(tmp, st.st_mode & 0o7777)
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(tmp, f)
        print(f"redacted {f}: {c}")
        total += c
        n += 1
    print(f"{n} files changed, {total} occurrences replaced")


if __name__ == "__main__":
    main()
