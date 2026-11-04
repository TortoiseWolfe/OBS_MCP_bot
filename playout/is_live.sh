#!/usr/bin/env bash
# is_live.sh <channel>   prints "live (api)", "offline (api)", "live (preview)" or "offline (preview)" (exit 0 live, 1 offline, 2 unknown)
# First choice: Twitch's API (helix/streams) through the private token helper, when it is present: it is true from the first second.
#   helper path: $TWITCH_HELPER, default ~/.config/afa/secrets/twitch_user.py (the token stays inside it; nothing here prints or passes it).
# Fallback, when the helper is missing or gives no answer: Twitch's public preview image. A live channel serves a JPEG (200); an offline
#   one redirects to a 404 placeholder. The image refreshes every 1 to 5 minutes and on 4 Nov stayed on the placeholder for 12+ minutes
#   after a start, so a preview "offline" right after a start or stop can be wrong; ask again a few minutes on.
set -u
ch="${1:?usage: is_live.sh <channel>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
helper="${TWITCH_HELPER:-$HOME/.config/afa/secrets/twitch_user.py}"
if [ -f "$helper" ]; then
  ans=$(timeout 60 python3 -I "$HERE/is_live_api.py" "$helper" "$ch" 2>/dev/null); rc=$?
  case "$rc" in
    0) echo "live (api)"; exit 0 ;;
    1) echo "offline (api)"; exit 1 ;;
  esac
fi
url="${IS_LIVE_PREVIEW_URL:-https://static-cdn.jtvnw.net/previews-ttv/live_user_${ch,,}-320x180.jpg}"
code=$(timeout 20 curl -s -o /dev/null -w '%{http_code}' "$url") || code=000
case "$code" in
  200) echo "live (preview)"; exit 0 ;;
  302|301|404) echo "offline (preview)"; exit 1 ;;
  *) echo "unknown (http $code)" >&2; exit 2 ;;
esac
