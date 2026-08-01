#!/bin/bash
# Entry point for the regatta stack.
#   Ubuntu 24.04 x86-64 : the stack runs directly, in this machine's LOTUSim
#                         environment -- the only platform install.sh can build.
#   anything else       : the same stack runs in a container.
# Override with RUNNER=native|docker.
# Usage: run_regatta.sh [duration_s] [hold|smoke] -- see -h.
set -u

usage() {
  cat << 'EOF'
usage: run_regatta.sh [duration] [hold|smoke]        (default: 120 hold)

Sails a 1 m RC sailboat around a two-buoy course, in simulation: xdyn computes
the physics, a ROS pilot steers, Gazebo ties them together. Headless by default.

  hold   watch it sail: bring the simulation up, leave it running for <duration>
         wall-clock seconds, then shut everything down.
  smoke  pass/fail check: did the boat round both buoys? Exits 0 or 1.
         <duration> is a budget in SIMULATED seconds -- a faster machine shortens
         the wait, never the verdict. One lap is about 243 simulated seconds.

env:
  UNITY=1   render it: open the ROS-TCP endpoint on :10000 and wait up to 120 s
            for the Unity scene to connect, so the start is not missed.
  WS_TAP=1  record every physics websocket exchange to ./_tap.jsonl.
  RUNNER=   native|docker. Default: native on Ubuntu 24.04 x86-64 (what
            install.sh targets), docker anywhere else.

examples:
  ./scripts/run_regatta.sh 400 smoke           # one asserted lap, ~4 min
  UNITY=1 ./scripts/run_regatta.sh 900 hold    # a quarter hour, rendered

Every wait in here is bounded -- a silent gz fails the smoke gate after 30 s
rather than hanging it. For a hard wall-clock cap on top, plain coreutils
works: timeout 1200 ./scripts/run_regatta.sh 900 hold

logs: /tmp/xdyn.log /tmp/gz.log /tmp/helm.log /tmp/endpoint.log
EOF
}
case "${1:-}" in -h | --help) usage; exit 0 ;; esac

DUR=${1:-120}
MODE=${2:-hold}
REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# "Linux" is not the requirement. Native needs ROS 2 Jazzy and an x86-64
# `xdyn-for-cs`, which is exactly install.sh's own gate. Route on that same rule:
# on Fedora, on Debian, on an arm64 Ubuntu, the native path dies in the preflight
# with "run install.sh" -- advice that cannot work there -- while the container
# would have carried the run.
native_supported() {
  [ "$(uname -m)" = x86_64 ] || return 1
  . /etc/os-release 2> /dev/null || return 1 # a subshell's copy: nothing leaks out
  [ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ]
}
RUNNER=${RUNNER:-$(native_supported && echo native || echo docker)}

if [ "$RUNNER" = "native" ]; then
  exec "$REGATTA_ROOT/scripts/regatta_stack.sh" "$DUR" "$MODE"
fi

# --- Docker path (macOS, and any Linux that is not the reference platform) ---
command -v docker > /dev/null || {
  echo "[!] this machine is not the native platform (install.sh needs Ubuntu 24.04"
  echo "[!] x86-64), and docker is not installed either. See README.md."
  exit 1
}
IMAGE=${IMAGE:-lotusim:focus-v2}
LAB=${LAB:-$(cd "$REGATTA_ROOT/.." && pwd)}
UNITY_PORT=; [ -n "${UNITY:-}" ] && UNITY_PORT="-p 10000:10000"
# Keep this host wrapper alive while Docker runs: the container's PID1 ignores
# SIGINT, so only the wrapper can turn the first Ctrl-C into a forced removal.
stop_container() {
  trap '' INT TERM
  docker rm -f regatta >/dev/null 2>&1
  exit "$1"
}
trap 'stop_container 130' INT
trap 'stop_container 143' TERM
# The image ships the core prebuilt at /lotusim_ws but sources none of it, so the
# container needs the environment install.sh would have left behind -- and env.sh
# is what builds it. It is sourced HERE rather than left to regatta_stack.sh's own
# "is the environment up?" guard, because in this image that guard is already
# satisfied and never fires: `LOTUSIM_WS`, `LOTUSIM_PATH` and `launch/` on PATH are
# baked in as image ENV, while `install/setup.bash` was never sourced. The run then
# starts, and dies 20 s in on `No module named 'lotusim_msgs'` in the helmsman.
#
# PYTHONPATH is the one thing env.sh cannot supply here: it puts src/ on the path
# (that is `regatta`), while `regatta_agents` comes from the colcon overlay a native
# machine has and this container does not. What is passed in is prepended to, never
# replaced by, env.sh.
REPO_IN_LAB="/lab/$(basename "$REGATTA_ROOT")"
docker run --rm --platform linux/amd64 --name regatta -v "$LAB":/lab \
  $UNITY_PORT \
  -e DUR="$DUR" -e MODE="$MODE" -e UNITY="${UNITY:-}" -e WS_TAP="${WS_TAP:-}" \
  -e LOTUSIM_WS=/lotusim_ws \
  -e PYTHONPATH="$REPO_IN_LAB/src/regatta_agents" \
  "$IMAGE" bash -lc \
  ". $REPO_IN_LAB/env.sh && $REPO_IN_LAB/scripts/regatta_stack.sh \"\$DUR\" \"\$MODE\"" &
wait "$!"
