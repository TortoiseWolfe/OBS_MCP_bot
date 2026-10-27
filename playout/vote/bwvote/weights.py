"""Rotation weights from the chat votes: liked songs come round more often, voted-down songs less.

A song needs MIN_VOTES distinct voters before its votes count (one stray vote must not move it). Its weight is
1 + 0.5 x (up - down), kept between MIN_WEIGHT and MAX_WEIGHT. A weight of 2 means two plays per round of the
list; 0.5 means one play every second round; 0.25 one every fourth. Nothing is ever dropped for good.
"""
MIN_VOTES = 2
MIN_WEIGHT, MAX_WEIGHT = 0.25, 3.0
ROUNDS = 12  # rounds written into one audio list; the list is rebuilt at every encoder restart


def weight(up, down):
    if up + down < MIN_VOTES:
        return 1.0
    return max(MIN_WEIGHT, min(MAX_WEIGHT, 1.0 + 0.5 * (up - down)))


def weights(songs, tally):
    return {s["id"]: weight(*tally.counts(s["id"])) for s in songs}


def signature(songs, tally):
    """What the schedule depends on; equal signatures give the same schedule."""
    w = weights(songs, tally)
    return tuple(w[s["id"]] for s in songs)


def sequence(songs, tally, rounds=ROUNDS, after_id=None):
    """The play order for `rounds` rounds. In each round a song due n times is spread evenly through the
    round (copy k of song i at (k + i/N) / n), so a liked song comes round at regular gaps, not in a clump."""
    w = weights(songs, tally)
    acc = {s["id"]: 0.0 for s in songs}
    seq, N = [], len(songs)
    for _ in range(rounds):
        slots = []
        for i, s in enumerate(songs):
            acc[s["id"]] += w[s["id"]]
            n = int(acc[s["id"]] + 1e-9)
            acc[s["id"]] -= n
            slots += [((k + i / N) / n, i, s) for k in range(n)]
        seq += [s for _, _, s in sorted(slots, key=lambda t: t[:2])]
    for i in range(1, len(seq) - 1):  # never the same song twice in a row
        if seq[i]["id"] == seq[i - 1]["id"]:
            seq[i], seq[i + 1] = seq[i + 1], seq[i]
    if after_id:  # carry on from the song after the one that was playing
        for i, s in enumerate(seq):
            if s["id"] == after_id:
                seq = seq[i + 1:] + seq[: i + 1]
                break
    return seq
