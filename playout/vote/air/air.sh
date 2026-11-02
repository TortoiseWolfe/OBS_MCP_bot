#!/bin/bash
# Puts one prerecorded film on the ScriptHammer Twitch channel as ONE ffmpeg process (-re = real time, -c copy = no re-encode).
# usage: air.sh film-a6 [START_SECONDS] [WAIT_UNTIL HH:MM today, 24-hour]
# The stream key is read from the key file at run time; never run ps or pgrep -a (they print the key).
# The key is on no command line: ffmpeg publishes to a local relay (relay/, an nginx RTMP container) at 127.0.0.1, and the relay's
# mode-600 config file (written by make-relay-conf.py) holds the Twitch address with the key. Not in argv, the log, the compose file or the image.
# The relay starts here and goes down when ffmpeg ends. Takes effect at the next airing; nothing already live is touched.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="${1:?film name, e.g. film-a6}"; SS="${2:-0}"; WAIT="${3:-}"
# AIR_ROOT, AIR_KEYFILE, AIR_RTMP_BASE, AIR_RELAY_PORT and AIR_RELAY_PROJECT exist only so the test can point the script at a throwaway folder, a fake key and a dead local port.
T="${AIR_ROOT:-/home/turtle_wolfe/band-wagon-tower}"; FILM="$T/replay/$TAG/film.mp4"; KEYF="${AIR_KEYFILE:-/home/turtle_wolfe/.config/afa/secrets/twitch-scripthammer.key}"; BASE="${AIR_RTMP_BASE:-rtmp://live.twitch.tv/app}"; PORT="${AIR_RELAY_PORT:-19350}"; PROJ="${AIR_RELAY_PROJECT:-bw-air-relay}"
[ -f "$FILM" ] || { echo "no film at $FILM"; exit 2; }
if [ -n "$WAIT" ]; then
  now=$(date +%s); at=$(date -d "today $WAIT" +%s)
  [ "$at" -gt "$now" ] && sleep $((at - now))
fi
if pgrep -f '^python3 run.py live' >/dev/null; then echo "REFUSED: the vote stream (run.py live) is still running"; exit 3; fi
if [ -f "$T/replay/air.pid" ] && kill -0 "$(cat "$T/replay/air.pid")" 2>/dev/null; then echo "REFUSED: a film is already on air (replay/air.pid)"; exit 4; fi
LOG="$T/replay/air-$TAG.log"
RUN="$T/replay/relay-run"; export RELAY_CONF="$RUN/nginx.conf" RELAY_PORT="$PORT"
compose() { timeout 120 docker compose -p "$PROJ" -f "$HERE/relay/compose.yml" "$@"; }
python3 "$HERE/make-relay-conf.py" "$KEYF" "$BASE" "$RELAY_CONF" > /dev/null || { echo "REFUSED: could not write the relay config"; exit 5; }
compose up -d --build > "$RUN/compose-up.log" 2>&1 || { echo "REFUSED: the relay did not start (see $RUN/compose-up.log)"; compose down > /dev/null 2>&1; exit 6; }
up=0; for _ in $(seq 1 60); do (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && { up=1; break; }; sleep 0.5; done
[ "$up" = 1 ] || { echo "REFUSED: the relay is not listening on 127.0.0.1:$PORT"; compose down > /dev/null 2>&1; exit 6; }
echo "$TAG" > "$T/replay/air.film"; date +%s > "$T/replay/air.start"; echo "$SS" > "$T/replay/air.offset"
: > "$LOG"
setsid nohup ffmpeg -nostdin -hide_banner -loglevel warning -stats -re -ss "$SS" -i "$FILM" -c copy -f flv "rtmp://127.0.0.1:$PORT/relay/air" > /dev/null 2> "$LOG" &
FPID=$!; echo $FPID > "$T/replay/air.pid"
setsid nohup bash -c 'while kill -0 "$1" 2>/dev/null; do sleep 5; done; shift; exec "$@"' _ "$FPID" timeout 120 docker compose -p "$PROJ" -f "$HERE/relay/compose.yml" down > /dev/null 2>&1 &
echo "$(date '+%-I:%M:%S %p') $TAG started at film second $SS through the local relay; log $LOG"
