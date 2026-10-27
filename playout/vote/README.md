# band-wagon-vote

Streams The Band Wagon song clips to a Twitch channel and lets chat vote on them. Chat types
`!up` or `!down` for the song on screen; the title, the live tally, the top songs and the next
song are drawn on the picture. Anything else typed in chat is ignored and never stored.

- Opens once with the full song named under `opener` in `playlist.json` (shown as "Opening the
  show Thursday", not voted on), then loops the 30 to 50 second clips.
- Votes: latest vote per viewer per song counts. Viewers are kept only as salted hashes.
  Totals are exported to `votes-twitch.json` (source "twitch"), beside, never over, the owner's
  own by-ear `votes.json`.
- One chat reader and one key redaction for the whole playout: `read_chat` in `../chat_tally.py` and `redact` in `../push.py`.
- Needs `ffmpeg`, `ffprobe` and Pillow on the host. The audio is not in this repo (private hub folder).

```bash
python3 run.py local --out /tmp/test.flv --seconds 20   # same picture and sound into a file
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

## Vote log, play log and weighting
- `state/votes.jsonl`: one line per counted `!up` / `!down`: clock time, song, seconds into that song, vote, and the viewer as a salted hash (never a name). `state/plays.jsonl`: one line per song start. Both use this machine's clock, read in the same process, so they line up without any conversion. A vote lands on the song a viewer was seeing, which is the encoder position minus `VOTE_LAG` (6 s).
- The play order follows the votes (`bwvote/weights.py`): weight = 1 + 0.5 x (up - down), between 0.25 and 3, and only once a song has 2 or more voters. A liked song comes round several times per round, evenly spaced; a voted-down one plays every second to fourth round; none is dropped for good.
- ffmpeg reads its audio list once, so new weights cannot apply mid-song. They apply at each encoder restart (a pause of about 10 s): at most once an hour, only if the weights changed, and only as a song is ending. The new order carries on from the song after the one that was playing.
