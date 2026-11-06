#!/bin/bash
# Runs inside the test OBS container (started by run.sh) once its websocket is up.
# Creates the hand-made "Content Attribution" text source the way an operator would,
# then runs every test marked requires_obs against this OBS and the stand-in stream server.
# Fails if anything fails, is skipped or errors: the point of this job is that none of them skip.
set -uo pipefail
cd /work

/opt/venv/bin/python -I - <<'PY'
from obswebsocket import obsws, requests as r

ws = obsws("localhost", 4455, "")
ws.connect()
res = ws.call(
    r.CreateInput(
        sceneName="Automated Content",
        inputName="Content Attribution",
        inputKind="text_ft2_source_v2",
        inputSettings={"text": "x"},
        sceneItemEnabled=True,
    )
)
assert res.status, res
ws.disconnect()
PY
[ $? -eq 0 ] || { echo "could not create the Content Attribution source"; exit 1; }

export OBS_BOT_OBS__WEBSOCKET_URL=ws://localhost:4455
export TWITCH_STREAM_KEY=dummy-test-key   # only a dummy: the stream goes to the stand-in server
export PYTHONDONTWRITEBYTECODE=1

out=$(mktemp)
/opt/venv/bin/python -m pytest tests -m requires_obs -o addopts="" -p no:cacheprovider -ra --tb=short -q -W ignore 2>&1 | tee "$out"
status=${PIPESTATUS[0]}
[ "$status" -eq 0 ] || exit "$status"

# The other tests (not marked requires_obs) run in the src tests job; here only these must all pass.
if grep -Eq '[0-9]+ (skipped|failed|error)' "$out"; then
  echo "a live-OBS test was skipped, failed or errored"
  exit 1
fi
echo "live-OBS tests: $(tail -1 "$out")"
