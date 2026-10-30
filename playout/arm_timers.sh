#!/usr/bin/env bash
# arm_timers.sh <thu|sat>   arm the two shows for Thu 29 Oct or Sat 31 Oct 2026 (replay).
# For each set: a push timer at the start time and a chat tally timer (same start). The push stops itself (-t).
# lane_timer.sh refuses a second timer with the same name, so a double arm is refused here too.
set -euo pipefail
cd "$(dirname "$0")"
day="${1:?usage: arm_timers.sh thu|sat}"
case "$day" in thu) date=2026-10-29 ;; sat) date=2026-10-31 ;; *) echo "thu or sat" >&2; exit 1 ;; esac
LT="$HOME/.claude/scripts/lane_timer.sh"
LOGS="$PWD/logs"; mkdir -p "$LOGS"
for set in set1 set2; do
  at=$(python3 -c "import json;print(json.load(open('sets/$set.json'))['live_start'][-5:])")
  mins=$(python3 -c "import json;print(json.load(open('sets/$set.json'))['live_minutes'])")
  name="bw-$day-$set"
  if "$LT" --list | grep -q "^$name-push: running"; then echo "refused: $name-push already armed" >&2; exit 3; fi
  "$LT" "$name-push" "$date $at" --log "$LOGS/$name-push.log" -- python3 "$PWD/push.py" "$set"
  "$LT" "$name-tally" "$date $at" --log "$LOGS/$name-tally.log" -- python3 "$PWD/chat_tally.py" "$LOGS/$name-tally.json" --seconds $((mins * 60))
done
"$LT" --list | grep "^bw-$day"
