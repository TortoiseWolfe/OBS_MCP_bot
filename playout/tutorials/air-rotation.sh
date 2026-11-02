#!/usr/bin/env bash
# Puts the 24/7 rotation on the ScriptHammer Twitch channel: ONE long-running ffmpeg receiver fed by rotate.py (-re = real time,
# -c copy = no re-encode). The list is air/reel-v1/list.json; rotate.py re-reads it at every item boundary, so a new list needs no restart.
# Like playout/vote/air/air.sh, the key is on no command line: the receiver publishes to a local relay at 127.0.0.1 whose
# mode-600 config (made by make-relay-conf.py) holds the Twitch address and key. Nothing here prints the key.
# usage: air-rotation.sh            (starts it; refuses if the vote stream, a film or a rotation is already on air)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; VOTE="$HERE/../vote/air"
AIR="${AIR_DIR:-/home/turtle_wolfe/clawd-twitch/air/reel-v1}"
KEYF="${AIR_KEYFILE:-/home/turtle_wolfe/.config/afa/secrets/twitch-scripthammer.key}"; BASE="${AIR_RTMP_BASE:-rtmp://live.twitch.tv/app}"
PORT="${AIR_RELAY_PORT:-19350}"; PROJ="${AIR_RELAY_PROJECT:-bw-air-relay}"
[ -f "$AIR/list.json" ] || { echo "no list at $AIR/list.json"; exit 2; }
if [ -f "$AIR/rotate.pid" ] && kill -0 "$(cat "$AIR/rotate.pid")" 2>/dev/null; then echo "REFUSED: the rotation is already on air"; exit 4; fi
if pgrep -f '^python3 run.py live' >/dev/null; then echo "REFUSED: the vote stream (run.py live) is still running"; exit 3; fi
RUN="$AIR/relay-run"; mkdir -p "$RUN"; export RELAY_CONF="$RUN/nginx.conf" RELAY_PORT="$PORT"
compose() { timeout 120 docker compose -p "$PROJ" -f "$VOTE/relay/compose.yml" "$@"; }
python3 "$VOTE/make-relay-conf.py" "$KEYF" "$BASE" "$RELAY_CONF" > /dev/null || { echo "REFUSED: could not write the relay config"; exit 5; }
compose up -d --build > "$RUN/compose-up.log" 2>&1 || { echo "REFUSED: the relay did not start (see $RUN/compose-up.log)"; compose down > /dev/null 2>&1; exit 6; }
# a real RTMP handshake, not just an open port: Docker opens the port before nginx is listening and resets early connections
python3 "$HERE/relay_ready.py" "$PORT" 40 || { echo "REFUSED: the relay did not answer an RTMP handshake on 127.0.0.1:$PORT"; compose down > /dev/null 2>&1; exit 6; }
setsid nohup python3 "$HERE/rotate.py" "$AIR/list.json" --out "rtmp://127.0.0.1:$PORT/relay/air" --status "$AIR/status.json" > /dev/null 2> "$AIR/rotate.log" &
RPID=$!; echo $RPID > "$AIR/rotate.pid"
setsid nohup bash -c 'while kill -0 "$1" 2>/dev/null; do sleep 5; done; shift; exec "$@"' _ "$RPID" timeout 120 docker compose -p "$PROJ" -f "$VOTE/relay/compose.yml" down > /dev/null 2>&1 &
echo "$(date '+%-I:%M:%S %p') rotation started through the local relay; status $AIR/status.json, log $AIR/rotate.log"
