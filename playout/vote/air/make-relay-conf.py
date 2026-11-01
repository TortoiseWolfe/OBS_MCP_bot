#!/usr/bin/env python3
"""Writes the relay's nginx.conf (mode 600) with the Twitch address in it.

usage: make-relay-conf.py KEYFILE BASE OUT        BASE = rtmp://live.twitch.tv/app
The key is read from KEYFILE and written only to OUT; it is never an argument and never printed.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    keyfile, base, out = sys.argv[1:4]
    key = "".join(Path(keyfile).read_text().split())
    if not key or not base.startswith("rtmp://"):
        sys.exit("make-relay-conf: need a key file with a key and an rtmp:// base")
    text = (HERE / "relay" / "nginx.conf.tmpl").read_text().replace("@@TARGET@@", f"{base.rstrip('/')}/{key}")
    out = Path(out)
    out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, out)
    print(f"wrote {out} (mode 600)")


if __name__ == "__main__":
    main()
