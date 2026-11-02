"""Pull frames out of a segment: one per second, sent on to the checks only when the picture changed (or 10 s passed).

ffmpeg decodes at 1 frame per second and pipes raw RGB. The caller gets (second, frame) for every frame that needs a
fresh look: the first, any whose 96x54 thumbnail differs from the last one handed over, and one at least every 10 s.
Identical frames reuse the last result, which is the same answer as checking each one.
"""
import json
import subprocess

import cv2
import numpy as np


def probe(path, timeout=60):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,duration,pix_fmt,bit_rate,sample_rate,channels:format=duration",
         "-of", "json", path], capture_output=True, text=True, timeout=timeout)
    return json.loads(out.stdout or "{}")


def fps_of(rate):
    a, _, b = (rate or "0/1").partition("/")
    try:
        return float(a) / float(b or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def thumb(frame):
    return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY), (96, 54), interpolation=cv2.INTER_AREA).astype(np.int16)


def iter_frames(path, width, height, step=1.0, change=1.0, max_gap=10.0, threads=2, settle=4.0):
    """Yield (t, frame, changed). `changed` is False for the periodic re-checks of an unchanged picture."""
    cmd = ["nice", "-n", "19", "timeout", "1800", "ffmpeg", "-nostdin", "-v", "error", "-threads", str(threads), "-i", path, "-vf", f"fps=1/{step}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = width * height * 3
    n, last, last_t = 0, None, -1e9
    pending, t_changed = None, 0.0  # a picture that has just changed and may still be fading in or out
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            t = n * step
            n += 1
            frame = np.frombuffer(buf, np.uint8).reshape(height, width, 3)
            th = thumb(frame)
            if pending is not None:
                # A frame taken mid-fade shows half-dim text, which reads as low contrast and half-empty slides.
                # Hand over the first frame of the new picture that has stopped moving (or the last one after `settle` s).
                # Count changed thumbnail pixels as well as the mean: one fading bullet is a few pixels, and the mean hides it.
                diff = np.abs(th - pending[2])
                still = float(diff.mean()) <= change and int((diff > 8).sum()) <= 4
                if still or t - t_changed >= settle:
                    last, last_t = th, t
                    pending = None
                    yield t, frame, True
                    continue
                pending = (t, frame.copy(), th)
                continue
            changed = last is None or float(np.abs(th - last).mean()) > change
            if changed:
                pending, t_changed = (t, frame.copy(), th), t
            elif t - last_t >= max_gap:
                last, last_t = th, t
                yield t, frame, False
        if pending is not None:
            yield pending[0], pending[1], True
    finally:
        p.stdout.close()
        p.kill()
        p.wait()
