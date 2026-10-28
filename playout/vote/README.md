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
python3 -m pytest -q -p no:cacheprovider tests
```

`--channel NAME` and `--key-file FILE` point it at another channel (for ScriptHammer: `--channel scripthammer --key-file ~/.config/afa/secrets/twitch-scripthammer.key`; never while a set from `push.py` is on that channel).

The picture is 720p at 5 frames a second with a keyframe every 2 seconds (Twitch needs one). The stream key is
read from the OBS profile named in `bwvote/ingest.py`, handed to ffmpeg, and never printed, logged or saved here.
It appears in ffmpeg's command line, so never run `ps` with full command lines while live.

## Pipe player
One ffmpeg encodes the show for hours. Its sound arrives on a continuous pipe (`bwvote/pipe.py`): a feeder thread decodes each take with its own ffmpeg to raw 48 kHz stereo and writes it into the encoder's stdin, counting bytes so each song's start time is exact. Right after a take starts, the player picks the next one (`bwvote/picker.py`), so no restart is needed to change the order, add a take or apply votes. If one take will not decode it is skipped and logged.

Catalog (`bwvote/catalog.py`): the songs in `playlist.json` plus `takes-catalog.json` (path under `"catalog"` in `playlist.json`), re-read at every pick:

```json
{"takes": [{"file": "bw-n13.mp3", "title": "Moonlit Marching Song", "group": "batch3", "feature": false, "hold": false}]}
```

- A catalog file is offered only after it has been unchanged for 15 s and is at least 5 s long (ffprobe), so a file still being written is never played.
- No title: shown as "Take <file name without bw- and .mp3>". `hold: true` keeps a take off air.
- Picker: no take repeats until every take has played (a cycle). Votes decide the order inside a cycle: weight = 1 + 0.5 x (up - down), between 0.25 and 3, once a take has 2 or more voters. A never-heard take counts three times (new ones come soon). Take weights below 1 sit a cycle out now and then; none is dropped for good. `state/picker.json` carries the cycle across restarts.
- Votes are recorded per take, so a new take starts at zero.

## Vote log and play log
- `state/votes.jsonl`: one line per counted `!up` / `!down`: clock time, song, seconds into that song, vote, and the viewer as a salted hash (never a name). `state/plays.jsonl`: one line per song start. Both use this machine's clock, read in the same process. A vote lands on the song a viewer was seeing, which is the encoder position minus `VOTE_LAG` (6 s).
- `BWVOTE_STATE=<folder>` moves all of `state/`, so an offline test run never touches a live one.
