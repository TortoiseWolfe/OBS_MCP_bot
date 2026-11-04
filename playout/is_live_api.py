#!/usr/bin/env python3
"""Asks Twitch's API (helix/streams) whether a channel is live, through the private helper that holds the user token.

usage: is_live_api.py HELPER_PY CHANNEL      prints live or offline; exit 0 = live, 1 = offline, 2 = no answer (helper missing or failed)

The helper (default ~/.config/afa/secrets/twitch_user.py) is loaded by path and only its helix(method, path, query) function is used;
it refreshes and sends the token itself. Nothing from the helper is printed (its output is discarded), so no token reaches a
command line, a log or this repo. Why not the preview image alone: on 4 Nov the preview stayed on the offline placeholder for
12+ minutes while helix/streams showed the channel live from the first second.
"""
import contextlib
import importlib.util
import io
import os
import sys


def stream_live(helper_path, channel):
    """True or False from helix/streams, None when there is no usable answer."""
    if not os.path.isfile(helper_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("twitch_user_helper", helper_path)
        mod = importlib.util.module_from_spec(spec)
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            spec.loader.exec_module(mod)
            code, data = mod.helix("GET", "/streams", {"user_login": channel.lower()})
    except BaseException:          # includes the helper's own sys.exit on a failed refresh; say nothing about why
        return None
    if code != 200 or not isinstance(data, dict) or "data" not in data:
        return None
    return any(s.get("type") == "live" for s in data["data"])


def main(argv):
    if len(argv) != 3:
        print("usage: is_live_api.py HELPER_PY CHANNEL", file=sys.stderr)
        return 2
    r = stream_live(argv[1], argv[2])
    if r is None:
        return 2
    print("live" if r else "offline")
    return 0 if r else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
