"""Encoder speed over a window, from fresh (output position, clock time) marks.

ffmpeg's own speed= figure averages everything since it started, so it cannot show the last minute; the window figure is the
output position gained divided by the clock time that passed, both read at the moment of each mark.
"""


class Window:
    def __init__(self):
        self.mark = None  # (output seconds, clock seconds) at the start of the current window

    def speed(self, pos, at):
        """Speed since the previous mark, then move the mark here. None on the first mark or if no time passed."""
        prev, self.mark = self.mark, (pos, at)
        if prev is None or at <= prev[1]:
            return None
        return (pos - prev[0]) / (at - prev[1])
