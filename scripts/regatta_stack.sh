#!/bin/bash
# The regatta stack: xdyn co-sim, helmsman, then gz -- in that order.
#
# Assumes it runs INSIDE a LOTUSim environment: `lotusim` on PATH, LOTUSIM_PATH
# set, this repo's overlay sourced. It knows nothing about the platform;
# run_regatta.sh decides whether that environment is local or a container.
#
# Usage: regatta_stack.sh [duration_s] [hold|smoke]
#   hold  = keep the stack up for the duration (interactive / Unity)  [default]
#   smoke = run the gz pose oracle as a pass/fail gate
# UNITY=1  also publish the ROS-TCP endpoint (:10000) and wait for Unity first.
# WS_TAP=1 insert a logging websocket tap between the gz plugin and xdyn.

DUR=${1:-120}
MODE=${2:-hold}
REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Run from a bare shell without ceremony: set the environment up ourselves when it
# is not already there. This script is bash, so env.sh picks the .bash flavours --
# the caller's own shell, zsh included, is never involved.
if [ -z "${LOTUSIM_PATH:-}" ] || ! command -v lotusim > /dev/null 2>&1; then
  [ -f "$REGATTA_ROOT/env.sh" ] || { echo "[!] $REGATTA_ROOT/env.sh is missing"; exit 1; }
  . "$REGATTA_ROOT/env.sh"
fi
# Being set is not enough: a half-built environment yields a plausible-looking
# path that fails 40s later as "no pose received" instead of as a bad setup.
[ -x "$LOTUSIM_PATH/physics/xdyn-for-cs" ] || {
  echo "[!] LOTUSIM_PATH=$LOTUSIM_PATH holds no physics/xdyn-for-cs -- run install.sh"; exit 1; }
command -v lotusim > /dev/null || {
  echo "[!] lotusim is not on PATH -- run install.sh, or . $REGATTA_ROOT/env.sh"; exit 1; }

# A gz left over from an earlier run keeps publishing on the same topics: the pose
# stream then carries two boats and the smoke gate believes whichever it sees first.
# It passed that way once. Refuse to start rather than produce a verdict about the
# wrong simulation.
# Ask gz, not the process table: `pgrep -f "gz sim"` matches any shell whose command
# line happens to contain that text, starting with the one that launched this script.
if timeout 10 gz topic -l 2>/dev/null | grep -q "^/world/lotusim/"; then
  echo "[!] something already publishes /world/lotusim topics -- a leftover run?"
  echo "[!] the pose stream would carry two boats. Stop it, then retry."
  exit 1
fi

XPID= GPID= HPID= WPID= EPID=
# `lotusim run` spawns gz as a CHILD, so killing $GPID alone orphans it (the old
# harness ran gz directly, where that was the same process). Kill the tree,
# deepest first, and with -9: gz ignores SIGTERM.
kill_tree(){
  local p
  for p in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$p"; done
  kill -9 "$1" 2>/dev/null
}
cleanup(){ local p; for p in $XPID $GPID $HPID $WPID $EPID; do kill_tree "$p"; done; }
trap cleanup EXIT

if [ -n "${UNITY:-}" ]; then
  # Endpoint first: Unity should be attached before the sim starts, so the
  # opening moments of the lap are rendered rather than missed.
  echo "[*] ros_tcp_endpoint on 0.0.0.0:10000"
  ros2 run ros_tcp_endpoint default_server_endpoint \
    --ros-args -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000 > /tmp/endpoint.log 2>&1 & EPID=$!
  for _ in $(seq 1 24); do
    grep -q "Connection from" /tmp/endpoint.log 2>/dev/null && { echo "[*] Unity connected"; break; }
    echo "[*] waiting for Unity (open the Regatta scene, press Play)..."
    sleep 5
  done
  grep -q "Connection from" /tmp/endpoint.log 2>/dev/null || \
    echo "[!] WARNING: no Unity connection after 120s -- continuing headless."
fi

# xdyn co-sim. --dt 0.005 is the physics-proven step (0.02 diverges): do not tune it.
# Two YAML files: the core vessel model, then the scenario conditions, whose
# environment section replaces the core's demo breeze.
MODEL="$LOTUSIM_PATH/assets/models/focus_v2/focus_v2.yaml"
CONDITIONS="$REGATTA_ROOT/assets/conditions/regatta_conditions.yaml"
( cd "$LOTUSIM_PATH/assets/models" && LD_LIBRARY_PATH="$LOTUSIM_PATH/physics" \
  "$LOTUSIM_PATH/physics/xdyn-for-cs" "$MODEL" "$CONDITIONS" \
  -s rk4 --dt 0.005 -a 127.0.0.1 -p 12345 ) > /tmp/xdyn.log 2>&1 & XPID=$!
sleep 4

WORLD_ARG="regatta.world"
if [ -n "${WS_TAP:-}" ]; then
  python3 "$REGATTA_ROOT/scripts/ws_tap.py" --log "$REGATTA_ROOT/_tap.jsonl" \
    > /tmp/ws_tap.log 2>&1 & WPID=$!
  sleep 1
  sed "s|ws://127.0.0.1:12345|ws://127.0.0.1:9999|" \
    "$REGATTA_ROOT/assets/worlds/regatta.world" > /tmp/regatta_tap.world
  TAP_ASSETS=/tmp/regatta_tap_assets
  mkdir -p "$TAP_ASSETS/worlds" && cp /tmp/regatta_tap.world "$TAP_ASSETS/worlds/regatta.world"
  ASSETS_ARG="$TAP_ASSETS:$REGATTA_ROOT/assets"
else
  ASSETS_ARG="$REGATTA_ROOT/assets"
fi

# Helmsman BEFORE gz: it publishes vessel_cmd_array continuously, so xdyn has
# sheet and helm at the first physics step. Without it xdyn answers "Unable to
# find signal" and the plugin crashes parsing the reply.
python3 -u -m regatta_agents.helmsman > /tmp/helm.log 2>&1 & HPID=$!
sleep 3

lotusim --assets-path "$ASSETS_ARG" run "$WORLD_ARG" > /tmp/gz.log 2>&1 & GPID=$!
sleep 8

RC=0
if [ "$MODE" = "smoke" ]; then
  python3 -u "$REGATTA_ROOT/scripts/smoke_rounds_marks.py" "$DUR"; RC=$?
else
  sleep "$DUR"
fi

echo "=== XDYN (tail) ===";  tail -6  /tmp/xdyn.log
echo "=== GZ (tail) ===";    tail -12 /tmp/gz.log
echo "=== HELM (tail) ===";  tail -12 /tmp/helm.log
exit $RC
