#!/usr/bin/env bash
# is_live.sh <channel>   prints "live" or "offline" (exit 0 live, 1 offline, 2 unknown)
# Reads Twitch's public preview image: a live channel serves a JPEG (200); an offline one redirects to a 404 placeholder.
# The image refreshes about every 1 to 5 minutes, so right after a start or stop it can lag; ask again a few minutes on.
set -u
ch="${1:?usage: is_live.sh <channel>}"
code=$(timeout 20 curl -s -o /dev/null -w '%{http_code}' "https://static-cdn.jtvnw.net/previews-ttv/live_user_${ch,,}-320x180.jpg") || code=000
case "$code" in
  200) echo live; exit 0 ;;
  302|301|404) echo offline; exit 1 ;;
  *) echo "unknown (http $code)" >&2; exit 2 ;;
esac
