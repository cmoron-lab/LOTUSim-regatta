#!/bin/bash
# Headless regatta run: xdyn co-sim + gz(regatta.world) + helmsman, all in the
# lotusim:focus-v2 image (LOTUSim prebuilt at /lotusim_ws; models/patched lib from /lab).
# Usage: run_regatta.sh [duration_s] [hold|smoke]
#   hold  = keep the stack up for the duration (interactive / Unity)   [default]
#   smoke = run the gz pose oracle as a pass/fail gate (rounds both marks?)
set -u
DUR=${1:-120}
MODE=${2:-hold}
docker run --rm --platform linux/amd64 --name regatta -v ~/src/lotusim-lab:/lab \
  -e DUR="$DUR" -e MODE="$MODE" -e HELM_TEST="${HELM_TEST:-}" -e WS_TAP="${WS_TAP:-}" \
  lotusim:focus-v2 bash -lc '
    XPID= GPID= HPID= WPID=   # ROS setup.bash is not set -u safe; do not enable set -u here
    cleanup(){ kill -9 $XPID $GPID $HPID $WPID 2>/dev/null; }  # gz ignores SIGTERM -> SIGKILL
    trap cleanup EXIT
    source /opt/ros/jazzy/setup.bash
    source /lotusim_ws/install/setup.bash
    export GZ_SIM_SYSTEM_PLUGIN_PATH=/lotusim_ws/install/lib
    export GZ_SIM_RESOURCE_PATH=/lab/LOTUSim/assets/models:/lab/LOTUSim-regatta/assets/models
    export PYTHONPATH=/lab/LOTUSim-regatta/src/regatta_agents:${PYTHONPATH:-}
    # FastDDS shared-memory transport deadlocks the gz ROS2 plugins under Rosetta/amd64
    # emulation (gz hangs at init). Force UDP-only transport -> plugins load & run.
    export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
    # temp model: wind FROM North (direction 180), and start CLOSE-HAULED with way on
    # (psi 60deg, u 0.8) like the offline oracle -- a boat starting at rest bow-to-wind
    # sits in irons and cannot bear away (the sail cannot fill head-to-wind at zero speed).
    MODEL=/lab/LOTUSim-regatta/offline/_regatta_model.yaml
    python3 - <<PY
import re
s = open("/lab/LOTUSim/assets/models/focus_v2/focus_v2.yaml").read()
s = re.sub(r"(direction:\s*\{unit:\s*deg,\s*value:\s*)[-0-9.]+", r"\g<1>180.0", s, count=1)
s = re.sub(r"(psi:\s*\{value:\s*)0\.0(, unit: deg\}\s*# bow North)", r"\g<1>60.0\g<2>", s, count=1)
s = re.sub(r"(u:\s*\{value:\s*)0\.0(, unit: m/s\})", r"\g<1>0.8\g<2>", s, count=1)
open("/lab/LOTUSim-regatta/offline/_regatta_model.yaml", "w").write(s)
PY
    chmod +x /lab/LOTUSim/physics/xdyn-for-cs 2>/dev/null || true
    # xdyn co-sim: fine internal --dt (decoupling rule), rk4 mandatory (monotonic clock):
    ( cd /lab/LOTUSim/assets/models && LD_LIBRARY_PATH=/lab/LOTUSim/physics \
      /lab/LOTUSim/physics/xdyn-for-cs "$MODEL" -s rk4 --dt 0.001 -a 127.0.0.1 -p 12345 \
      ) > /tmp/xdyn.log 2>&1 & XPID=$!
    sleep 4
    WORLD=/lab/LOTUSim-regatta/assets/worlds/regatta.world
    if [ -n "$WS_TAP" ]; then
      # Passive ws logging tap: gz plugin -> :9999 (tap) -> :12345 (xdyn), passthrough logged as JSONL.
      python3 /lab/LOTUSim-regatta/scripts/ws_tap.py --log /lab/LOTUSim-regatta/_tap.jsonl \
        > /tmp/ws_tap.log 2>&1 & WPID=$!
      sleep 1
      sed "s|ws://127.0.0.1:12345|ws://127.0.0.1:9999|" "$WORLD" > /tmp/regatta_tap.world
      WORLD=/tmp/regatta_tap.world
    fi
    # Start the helmsman BEFORE gz. As a ROS2 node it (a) pre-creates a DDS participant in
    # the domain -- under Rosetta the gz plugins deadlock creating the FIRST participant, so
    # one must already exist -- and (b) publishes vessel_cmd_array continuously, so xdyn
    # always has mainsail(sheet)/rudder(helm) when the physics plugin takes its first step
    # (otherwise xdyn errors "Unable to find signal" and the plugin crashes parsing the reply).
    python3 -u -m regatta_agents.helmsman > /tmp/helm.log 2>&1 & HPID=$!
    sleep 3
    [ -f /lab/LOTUSim-regatta/_patched_lib/libphysics_interface_plugin.so ] && \
      cp /lab/LOTUSim-regatta/_patched_lib/libphysics_interface_plugin.so /lotusim_ws/install/lib/
    gz sim -s -r "$WORLD" > /tmp/gz.log 2>&1 & GPID=$!
    sleep 8
    RC=0
    if [ "$MODE" = "smoke" ]; then
      python3 -u /lab/LOTUSim-regatta/scripts/smoke_rounds_marks.py "$DUR"; RC=$?
    else
      sleep "$DUR"
    fi
    echo "=== XDYN (tail) ===";  tail -6  /tmp/xdyn.log
    echo "=== GZ (tail) ===";    tail -12 /tmp/gz.log
    echo "=== HELM (tail) ===";  tail -12 /tmp/helm.log
    exit $RC
  '
