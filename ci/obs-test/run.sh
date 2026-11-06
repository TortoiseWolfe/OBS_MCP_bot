#!/bin/bash
# Headless test OBS for the live-OBS tests (see .github/workflows/tests.yml, job obs-tests).
# Own profile and scene collection, websocket on 4455 inside the container only, no password.
# With STANDIN_RTMP set, the stream target is that server and a dummy key; otherwise there is no stream service.
# Never Twitch: the container sits on a Docker network with no outside access.
set -e
C=$HOME/.config/obs-studio
mkdir -p $C/basic/profiles/TestProfile $C/basic/scenes $C/plugin_config/obs-websocket
cat > $C/global.ini <<G
[General]
FirstRun=true
[Basic]
Profile=TestProfile
ProfileDir=TestProfile
SceneCollection=TestScenes
SceneCollectionFile=TestScenes
[OBSWebSocket]
FirstLoad=false
ServerEnabled=true
ServerPort=4455
AlertsEnabled=false
AuthRequired=false
G
cat > $C/basic/profiles/TestProfile/basic.ini <<G
[General]
Name=TestProfile
[Video]
BaseCX=1280
BaseCY=720
OutputCX=1280
OutputCY=720
FPSType=0
FPSCommon=30
[Output]
Mode=Simple
G
cat > $C/basic/scenes/TestScenes.json <<G
{"name":"TestScenes","current_scene":"Automated Content","current_program_scene":"Automated Content","scene_order":[{"name":"Automated Content"},{"name":"Owner Live"},{"name":"Failover"}],"sources":[{"id":"scene","name":"Automated Content","settings":{"items":[]},"versioned_id":"scene"},{"id":"scene","name":"Owner Live","settings":{"items":[]},"versioned_id":"scene"},{"id":"scene","name":"Failover","settings":{"items":[]},"versioned_id":"scene"}]}
G
cat > $C/plugin_config/obs-websocket/config.json <<G
{"alerts_enabled":false,"auth_required":false,"first_load":false,"server_enabled":true,"server_password":"","server_port":4455,"AlertsEnabled":false,"AuthRequired":false,"FirstLoad":false,"ServerEnabled":true,"ServerPassword":"","ServerPort":4455}
G
if [ -n "${STANDIN_RTMP:-}" ]; then
  # Stand-in stream server on the private test network (never Twitch); dummy key.
  cat > $C/basic/profiles/TestProfile/service.json <<G
{"type":"rtmp_custom","settings":{"server":"$STANDIN_RTMP","key":"dummy-test-key","use_auth":false}}
G
  cat > $C/basic/profiles/TestProfile/basic.ini <<G
[General]
Name=TestProfile
[Video]
BaseCX=640
BaseCY=360
OutputCX=640
OutputCY=360
FPSType=0
FPSCommon=15
[Output]
Mode=Simple
[SimpleOutput]
VBitrate=400
ABitrate=64
StreamEncoder=x264
Preset=ultrafast
G
else
  rm -f $C/basic/profiles/TestProfile/service.json
fi
export LIBGL_ALWAYS_SOFTWARE=1
xvfb-run -a -s "-screen 0 1280x720x24" obs --disable-shutdown-check --disable-updater --profile TestProfile --collection TestScenes
