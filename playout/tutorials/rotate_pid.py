#!/usr/bin/env python3
"""Is the number in rotate.pid really a running rotate.py? Removes the pid file when it is not.

Why: a pid file outlives a reboot, and after the reboot the same number can belong to an unrelated process. On 4 Nov the
guard in air-rotation.sh (kill -0 only) saw a live process, refused with "already on air", and the hub had to remove the file
by hand. This looks at the process's own command-line record in /proc for the word rotate.py. It looks for that one word
and prints nothing from the record.

usage: rotate_pid.py PIDFILE      exit 0 = a rotate.py is running under that pid (leave the file);
                                  exit 1 = no pid file, or the process is gone or is not rotate.py (a stale file is removed)
"""
import os
import sys

MARK = "rotate.py"


def is_rotate(pid, proc="/proc"):
    """True when process `pid` exists and one of its command-line words is rotate.py (or a path ending in it)."""
    try:
        with open(os.path.join(proc, str(pid), "cmdline"), "rb") as f:
            raw = f.read()
    except OSError:
        return False
    return any(w == MARK or w.endswith("/" + MARK) for w in raw.decode("utf-8", "replace").split("\0"))


def check(pidfile, proc="/proc"):
    """0 when the pid file names a running rotate.py. Otherwise 1, and a stale pid file is deleted."""
    try:
        text = open(pidfile).read().strip()
    except OSError:
        return 1
    if text.isdigit() and int(text) > 0 and is_rotate(int(text), proc):
        return 0
    try:
        os.remove(pidfile)
    except OSError:
        pass
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: rotate_pid.py PIDFILE")
    sys.exit(check(sys.argv[1]))
