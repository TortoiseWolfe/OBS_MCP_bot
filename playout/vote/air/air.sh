#!/bin/bash
# Puts one prerecorded film on the ScriptHammer Twitch channel as ONE ffmpeg process (-re = real time, -c copy = no re-encode).
# usage: air.sh film-a6 [START_SECONDS] [WAIT_UNTIL HH:MM today, 24-hour]
# The stream key is read from the key file at run time; never run ps or pgrep -a (they print the key).
# The log never holds the key: ffmpeg runs at -loglevel warning (no "Output #0 ... to rtmp://..." line), and its messages go
# through redact-stream.py, which swaps the key for [stream-key] if an error message ever repeats the address.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="${1:?film name, e.g. film-a6}"; SS="${2:-0}"; WAIT="${3:-}"
# AIR_ROOT, AIR_KEYFILE and AIR_RTMP_BASE exist only so the test can point the script at a throwaway folder, a fake key and a dead local port.
T="${AIR_ROOT:-/home/turtle_wolfe/band-wagon-tower}"; FILM="$T/replay/$TAG/film.mp4"; KEYF="${AIR_KEYFILE:-/home/turtle_wolfe/.config/afa/secrets/twitch-scripthammer.key}"; BASE="${AIR_RTMP_BASE:-rtmp://live.twitch.tv/app}"
[ -f "$FILM" ] || { echo "no film at $FILM"; exit 2; }
if [ -n "$WAIT" ]; then
  now=$(date +%s); at=$(date -d "today $WAIT" +%s)
  [ "$at" -gt "$now" ] && sleep $((at - now))
fi
if pgrep -f '^python3 run.py live' >/dev/null; then echo "REFUSED: the vote stream (run.py live) is still running"; exit 3; fi
if [ -f "$T/replay/air.pid" ] && kill -0 "$(cat "$T/replay/air.pid")" 2>/dev/null; then echo "REFUSED: a film is already on air (replay/air.pid)"; exit 4; fi
LOG="$T/replay/air-$TAG.log"
URL="$BASE/$(tr -d '[:space:]' < "$KEYF")"
echo "$TAG" > "$T/replay/air.film"; date +%s > "$T/replay/air.start"; echo "$SS" > "$T/replay/air.offset"
: > "$LOG"
setsid nohup ffmpeg -nostdin -hide_banner -loglevel warning -stats -re -ss "$SS" -i "$FILM" -c copy -f flv "$URL" > /dev/null 2> >(python3 "$HERE/redact-stream.py" "$KEYF" >> "$LOG") &
echo $! > "$T/replay/air.pid"
echo "$(date '+%-I:%M:%S %p') $TAG started at film second $SS; log $LOG"
