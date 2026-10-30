# CLAUDE.md

Fan-vote Twitch stream for the Band Wagon clips. Read `README.md` first.

- Stdlib Python plus host `ffmpeg` and Pillow. No installs. Tests: `python3 -m pytest -q -p no:cacheprovider tests`.
- The stream key is read only in `bwvote/ingest.py`. Never print it, never write it to a file or log, never run `ps` with full
  command lines (ffmpeg's arguments hold it). Log lines pass through `ingest.redact`.
- `state/` (or `$BWVOTE_STATE`) is gitignored runtime data (tally, overlay text, pid, log, picker cycle). A running stream reads files from this checkout: do not delete or switch away from the folder while live.
- Viewers are salted hashes only; never store or show a chat name or any chat text except the `!up` / `!down` command.
- Audience is general and kid-friendly: keep titles, overlay and chat output clean.
- The owner's by-ear votes (`votes.json`) are never touched.
