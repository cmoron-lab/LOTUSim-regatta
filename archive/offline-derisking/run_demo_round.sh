#!/bin/bash
# Unity demo backend (run INSIDE lotusim:focus-v2-bridge):
#   ros_tcp_endpoint (bridge to native macOS Unity) -> WAIT for Unity -> xdyn -> gz -> helmsman.
# The Focus V2 sailboat sails up to the race mark and ROUNDS it (closest ~0.1-0.2 m),
# streamed to native Unity (Metal) over /defenseScenario/renderer_*.
#
# Ordering & transport are NOT optional (see docs/macos-demo.md):
#   * connect-first  (§5.4): endpoint stays idle until Unity connects, THEN gz starts, else the
#                            single-threaded endpoint's accept() is GIL-starved by gz's 20 Hz flood.
#   * FASTDDS=DEFAULT (§5.5): re-enables SHM so the endpoint (subscriber-first) matches gz's
#                            later publishers inside the container.
#   * dt = 0.02      : xdyn diverges (NaN -> gz Abort) at dt 0.05 once the controller commands the
#                      hard turn needed to CLOSE the loop. 0.02 is stable through the turn.
#   * kp=1.4 rudmax=1.0 : enough rudder authority to round the mark tightly (~1.1 m) and come back
#                      (a CLOSED loop). Lower authority -> open curve; see _offline/CLOSED_LOOP_RECIPE.md.
set +e
source /opt/ros/jazzy/setup.bash
source /lotusim_ws/install/setup.bash 2>/dev/null
export GZ_SIM_SYSTEM_PLUGIN_PATH=/lotusim_ws/install/lib
export GZ_SIM_RESOURCE_PATH=/lotusim_ws/src/LOTUSim/assets/models
export FASTDDS_BUILTIN_TRANSPORTS=DEFAULT
chmod +x /lotusim_ws/src/LOTUSim/physics/* 2>/dev/null

LAB=/lab/_offline
WORLDF=$LAB/focus_v2_unity_round.world
WAIT_UNITY=${WAIT_UNITY:-600}
DT=${DT:-0.02}; SIGN=${SIGN:--1.0}; KP=${KP:-1.4}; RUDMAX=${RUDMAX:-1.0}
RUN_SECS=${RUN_SECS:-3600}

cleanup(){ echo "[*] cleanup"; kill $EP $XDYN $GZ $HELM 2>/dev/null; }
trap cleanup EXIT INT TERM

echo "[*] ros_tcp_endpoint on 0.0.0.0:10000"
ros2 run ros_tcp_endpoint default_server_endpoint \
  --ros-args -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000 >/tmp/endpoint.log 2>&1 &
EP=$!

echo "[*] >>> Press Play in Unity now — waiting for it to connect to the idle endpoint <<<"
for i in $(seq 1 "$WAIT_UNITY"); do
  grep -q "Connection from" /tmp/endpoint.log && { echo "[*] Unity connected after ${i}s — starting co-sim"; break; }
  sleep 1
done

cd /lotusim_ws/src/LOTUSim/assets/models
echo "[*] xdyn-for-cs focus_v2 :12345 dt=$DT"
xdyn-for-cs focus_v2/focus_v2.yaml --address 127.0.0.1 --port 12345 --dt "$DT" -s rk4 >/tmp/xdyn.log 2>&1 &
XDYN=$!; sleep 4

echo "[*] gz sim -s -r focus_v2_unity_round.world (headless, render=ROS2)"
gz sim -s -r "$WORLDF" >/tmp/gz.log 2>&1 &
GZ=$!; sleep 8
echo "=== handshake ==="; grep -iE "Creation detected|Surface init completed|onOpen|onFail" /tmp/gz.log | head

echo "[*] ctrl_course (rounds the mark at 0,12 -> closed loop) world=defenseScenario sign=$SIGN kp=$KP rudmax=$RUDMAX"
python3 $LAB/ctrl_course.py --world defenseScenario --sign "$SIGN" --kp "$KP" --rudmax "$RUDMAX" >/tmp/helm.log 2>&1 &
HELM=$!

echo "[*] running ${RUN_SECS}s — 'docker stop fv2round' to end. Tail: docker logs -f fv2round"
sleep "$RUN_SECS"
