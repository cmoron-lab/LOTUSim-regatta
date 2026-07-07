#!/bin/bash
# Headless regatta run: xdyn co-sim + gz(regatta.world) + helmsman, all in the
# lotusim:focus-v2 image (LOTUSim prebuilt at /lotusim_ws; models/patched lib from /lab).
# Usage: run_regatta.sh [duration_s] [hold|smoke]
#   hold  = keep the stack up for the duration (interactive / Unity)   [default]
#   smoke = run the gz pose oracle as a pass/fail gate (rounds both marks?)
# UNITY=1 (non-empty): also publish the ROS-TCP endpoint (port 10000) and wait for
#   Unity to connect before starting xdyn/gz/helmsman -- image has ros_tcp_endpoint
#   built in (colcon build --packages-select ros_tcp_endpoint, vendored from
#   LOTUSim-Unity-modules/Submodules/ROS-TCP-Endpoint).
set -u
DUR=${1:-120}
MODE=${2:-hold}
# Ctrl-C must kill the container: in-container bash is PID1 and ignores SIGINT,
# so the EXIT cleanup trap never fires without this host-side backstop.
trap 'docker rm -f regatta >/dev/null 2>&1' INT TERM
UNITY_PORT=
[ -n "${UNITY:-}" ] && UNITY_PORT="-p 10000:10000"
docker run --rm --platform linux/amd64 --name regatta -v ~/src/lotusim-lab:/lab \
  $UNITY_PORT \
  -e DUR="$DUR" -e MODE="$MODE" -e HELM_TEST="${HELM_TEST:-}" -e WS_TAP="${WS_TAP:-}" \
  -e UNITY="${UNITY:-}" \
  lotusim:focus-v2 bash -lc '
    XPID= GPID= HPID= WPID= EPID=   # ROS setup.bash is not set -u safe; do not enable set -u here
    cleanup(){ kill -9 $XPID $GPID $HPID $WPID $EPID 2>/dev/null; }  # gz ignores SIGTERM -> SIGKILL
    trap cleanup EXIT
    source /opt/ros/jazzy/setup.bash
    source /lotusim_ws/install/setup.bash
    export GZ_SIM_SYSTEM_PLUGIN_PATH=/lotusim_ws/install/lib
    export GZ_SIM_RESOURCE_PATH=/lab/LOTUSim/assets/models:/lab/LOTUSim-regatta/assets/models
    export PYTHONPATH=/lab/LOTUSim-regatta/src/regatta_agents:${PYTHONPATH:-}
    # FastDDS shared-memory transport deadlocks the gz ROS2 plugins under Rosetta/amd64
    # emulation (gz hangs at init). Force UDP-only transport -> plugins load & run.
    export FASTDDS_BUILTIN_TRANSPORTS=UDPv4
    if [ -n "$UNITY" ]; then
      # Endpoint first, before anything else (even xdyn): it doubles as the
      # preexisting DDS participant that unblocks Rosetta (see helmsman-before-gz
      # comment below) -- xdyn -> helmsman -> gz order is otherwise unchanged.
      echo "[*] ros_tcp_endpoint on 0.0.0.0:10000"
      ros2 run ros_tcp_endpoint default_server_endpoint \
        --ros-args -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000 > /tmp/endpoint.log 2>&1 & EPID=$!
      for _ in $(seq 1 24); do
        grep -q "Connection from" /tmp/endpoint.log 2>/dev/null && { echo "[*] Unity connected"; break; }
        echo "[*] waiting for Unity (open the Regatta scene, press Play)..."
        sleep 5
      done
      grep -q "Connection from" /tmp/endpoint.log 2>/dev/null || \
        echo "[!] WARNING: no Unity connection after 120s -- continuing headless (rendering will be missing, sim runs)."
    fi
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
    # xdyn co-sim: --dt 0.005 = the physics-proven step (offline de-risking + oracle),
    # 2 substeps per 0.01 comm step. One rk4 substep costs ~3.1 ms under Rosetta, so
    # --dt drives the RTF ceiling (0.001 capped RTF at ~0.3; 0.005 reaches ~1.0).
    ( cd /lab/LOTUSim/assets/models && LD_LIBRARY_PATH=/lab/LOTUSim/physics \
      /lab/LOTUSim/physics/xdyn-for-cs "$MODEL" -s rk4 --dt 0.005 -a 127.0.0.1 -p 12345 \
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
