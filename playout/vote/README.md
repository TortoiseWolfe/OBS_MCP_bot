# band-wagon-vote

Streams The Band Wagon song clips to a Twitch channel and lets chat vote on them. Chat types
`!up` or `!down` for the song on screen; the title, the live tally, the top songs and the next
song are drawn on the picture. Anything else typed in chat is ignored and never stored.

- Plays full takes one after another from a catalog (see "Pipe player"). An `opener` in `playlist.json` plays once at the start (not voted on) unless `--no-opener`.
- Votes: latest vote per viewer per song counts. Viewers are kept only as salted hashes.
  Totals are exported to `votes-twitch.json` (source "twitch"), beside, never over, the owner's
  own by-ear `votes.json`.
- One chat reader and one key redaction for the whole playout: `read_chat` in `../chat_tally.py` and `redact` in `../push.py`.
- Needs `ffmpeg`, `ffprobe` and Pillow on the host. The audio is not in this repo (private hub folder).

```bash
python3 run.py local --out /tmp/test.flv --seconds 20   # same picture and sound into a file
BWVOTE_STATE=/tmp/bw-state python3 run.py local --playlist other.json --out /tmp/t.flv --seconds 100   # offline run beside a live one
python3 run.py live --bandwidthtest --seconds 60        # Twitch speed test, nothing public
python3 run.py live                                     # go live
python3 run.py report                                   # hourly tally line
python3 run.py stop
python3 run.py bottom                                   # takes voted to the bottom
python3 run.py purge TAKE_ID --reason "..."             # move a take aside (file kept in _purged, never deleted)
python3 run.py purge --restore TAKE_ID                  # bring it back
python3 run.py control                                  # purge control page; set "control": {"allow", "bind", "port": 8780, optional "forwarders" and "hosts" behind a port forward (see bwvote/control.py)} in playlist.json
python3 -m pytest -q -p no:cacheprovider tests
```

`--channel NAME` and `--key-file FILE` point it at another channel (for ScriptHammer: `--channel scripthammer --key-file ~/.config/afa/secrets/twitch-scripthammer.key`; never while a set from `push.py` is on that channel).

The picture is 720p at 5 frames a second with a keyframe every 2 seconds (Twitch needs one). The stream key is
read from the OBS profile named in `bwvote/ingest.py`, handed to ffmpeg, and never printed, logged or saved here.
It appears in ffmpeg's command line, so never run `ps` with full command lines while live.

## Pipe player
One ffmpeg encodes the show for hours. Its sound arrives on a continuous pipe (`bwvote/pipe.py`): a feeder thread decodes each take with its own ffmpeg to raw 48 kHz stereo and writes it into the encoder's stdin, counting bytes so each song's start time is exact. Right after a take starts, the player picks the next one (`bwvote/picker.py`), so no restart is needed to change the order, add a take or apply votes. If one take will not decode it is skipped and logged.

Catalog (`bwvote/catalog.py`): the songs in `playlist.json` plus the take factory's own catalog (`beatboard/tools/factory/take_factory.py`), read exactly as the factory writes it, from the path under `"catalog"` in `playlist.json` (`<band-wagon audio>/takes/catalog.json`), re-read at every pick. There is no second catalog. The factory's file is a list, one entry per finished take; the player uses `take`, `song`, `path` and `kind`:

```json
[{"song": "story-1", "take": "story-1-t3", "take_n": 3, "style": "...", "seed": 12345, "bpm": 76, "seconds": 215.0, "path": "/abs/story-1-t3.mp3", "kind": "story"}]
```

- Titles come from `songs.json` beside it (the factory's registry): "The Riders, take 3". The picture shows that title.
- A take is offered only after its file has been unchanged for 15 s and is at least 5 s long (ffprobe), so one still being written is never played. `"hold": true` on an entry keeps it off air.
- Votes are kept per take. In `votes-twitch.json` each take is listed, and its votes are also added to its song (key = the factory's song id), which is what the factory reads to decide which song to render more of.
- Picker: no take repeats until every take has played (a cycle). Votes decide the order inside a cycle: weight = 1 + 0.5 x (up - down), between 0.25 and 3, once a take has 2 or more voters. A never-heard take counts three times (new ones come soon). Take weights below 1 sit a cycle out now and then; none is dropped for good. `state/picker.json` carries the cycle across restarts.
- Votes are recorded per take, so a new take starts at zero.

## Vote log and play log
- `state/votes.jsonl`: one line per counted `!up` / `!down`: clock time, song, seconds into that song, vote, and the viewer as a salted hash (never a name). `state/plays.jsonl`: one line per song start. Both use this machine's clock, read in the same process. A vote lands on the song a viewer was seeing, which is the encoder position minus `VOTE_LAG` (6 s).
- `BWVOTE_STATE=<folder>` moves all of `state/`, so an offline test run never touches a live one.
