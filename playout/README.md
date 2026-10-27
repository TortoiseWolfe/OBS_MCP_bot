# Band Wagon playout (ffmpeg direct)

Plays The Band Wagon (an AI robot band) to Twitch with no OBS and no one at the keyboard. The existing OBS
controller in `src/` needs a running OBS to drive; this folder sends a pre-rendered loop file straight to Twitch.

| File | What it does |
|---|---|
| `sets/set1.json`, `sets/set2.json` | The set lists: songs in order, a vote card after both duet takes, the hook last, start time, length |
| `build_loop.py` | Renders `out/<set>-loop.mp4` (1280x720, 30 fps, keyframe every 2 s, CBR 3,500 kbps, AAC 160 kbps 48 kHz, each song at -16 LUFS) |
| `push.py` | `-stream_loop -1 -re -c copy -t <set length>` to Twitch. Reads the key only here; every log line is redacted |
| `chat_tally.py` | Read-only anonymous chat reader (justinfan login, no token); counts "1" and "2" into a JSON file |
| `is_live.sh` | `is_live.sh scripthammer` prints live or offline |
| `arm_timers.sh` | `arm_timers.sh thu` or `sat` arms the push and tally timers; a second arm is refused |
| `vote/` | Live fan-vote stream: loops the Band Wagon clips with the song title and a live `!up` / `!down` tally on screen. Reads chat through `chat_tally.read_chat` and hides the key with `push.redact`; see `vote/README.md` |

## Run it

```
python3 playout/build_loop.py playout/sets/set1.json     # then set2.json; needs ffmpeg and Pillow
python3 playout/push.py set1 --bandwidthtest --seconds 300   # invisible test to the real ingest
playout/arm_timers.sh thu                                 # Thu 29 Oct 5:58 PM and 7:58 PM Eastern
playout/arm_timers.sh sat                                 # Sat 31 Oct replay, same times
```

The stream key lives in `~/.config/afa/secrets/twitch-scripthammer.key` (mode 600) and is never printed.
`push.py` refuses a real push (no `--bandwidthtest`) before Thu 29 Oct 5:57 PM Eastern.

## Notes

- To change the songs, edit the `items` list in the set file and rebuild; the timers read the loop file when they fire.
- Set 1 stops itself at 7:30 PM (92 min), set 2 at 10:00 PM (122 min). Each loop is about 4 min 5 s.
- `is_live.sh` reads Twitch's public preview image, which can lag a few minutes after a start or stop.
- Tests: `python3 -m pytest -c /dev/null --rootdir=. playout/tests`
