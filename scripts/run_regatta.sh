#!/bin/bash
# Entry point for the regatta stack.
#   Linux : the stack runs directly, in the LOTUSim environment of this machine.
#   macOS : ROS and gz cannot run natively, so the same stack runs in a container.
# Override with RUNNER=native|docker.
# Usage: run_regatta.sh [duration_s] [hold|smoke]
set -u
DUR=${1:-120}
MODE=${2:-hold}
REGATTA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER=${RUNNER:-$([ "$(uname -s)" = "Linux" ] && echo native || echo docker)}

if [ "$RUNNER" = "native" ]; then
  exec "$REGATTA_ROOT/scripts/regatta_stack.sh" "$DUR" "$MODE"
fi

# --- Docker path (macOS) ---------------------------------------------------
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
