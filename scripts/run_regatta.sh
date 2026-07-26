#!/bin/bash
# Entry point for the regatta stack.
#   Ubuntu 24.04 x86-64 : the stack runs directly, in this machine's LOTUSim
#                         environment -- the only platform install.sh can build.
#   anything else       : the same stack runs in a container.
# Override with RUNNER=native|docker.
# Usage: run_regatta.sh [duration_s] [hold|smoke]
set -u
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
# In-container bash is PID1 and ignores SIGINT, so the EXIT trap never fires
# without this host-side backstop.
trap 'docker rm -f regatta >/dev/null 2>&1' INT TERM
# The image ships the core prebuilt at /lotusim_ws but exports none of it, and it
# has no overlay: the repo is mounted, never colcon-built. So the container gets
# by environment what a native machine gets from install.sh. UNVERIFIED on macOS
# since this branch was written -- Task 9 of the plan is the run that settles it.
REPO_IN_LAB="/lab/$(basename "$REGATTA_ROOT")"
exec docker run --rm --platform linux/amd64 --name regatta -v "$LAB":/lab \
  $UNITY_PORT \
  -e DUR="$DUR" -e MODE="$MODE" -e UNITY="${UNITY:-}" -e WS_TAP="${WS_TAP:-}" \
  -e LOTUSIM_WS=/lotusim_ws -e LOTUSIM_PATH=/lotusim_ws/src/LOTUSim \
  -e PYTHONPATH="$REPO_IN_LAB/src/regatta_agents" \
  "$IMAGE" bash -lc \
  "export PATH=\"\$LOTUSIM_PATH/launch:\$PATH\"; $REPO_IN_LAB/scripts/regatta_stack.sh \"\$DUR\" \"\$MODE\""
