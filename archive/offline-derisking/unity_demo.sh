#!/usr/bin/env bash
# Pilote la demo Unity du voilier Focus V2 (backend conteneur : ctrl_course + modele yawdamp).
#
#   ./unity_demo.sh            (re)lance le backend et attend Unity   <- l'usage principal
#   ./unity_demo.sh stop       arrete le backend
#   ./unity_demo.sh logs       suit les logs du backend (Ctrl+C pour quitter)
#   ./unity_demo.sh traj       releve la trajectoire (headless) + points de placement bouee
#
# Apres './unity_demo.sh' : dans Unity, pose la bouee, Play, suis focus_v2 (Shift+F).
set -e
NAME=fv2round
LAB="$HOME/src/lotusim-lab"
IMG=lotusim:focus-v2-bridge
MOUNTS=(-v "$LAB/LOTUSim:/lotusim_ws/src/LOTUSim" -v "$LAB:/lab")

case "${1:-run}" in
  stop)
    docker rm -f "$NAME" >/dev/null 2>&1 && echo "[*] backend arrete." || echo "[*] aucun backend en cours."
    ;;

  logs)
    docker logs -f "$NAME"
    ;;

  traj)
    echo "[*] releve de trajectoire (run headless ~100 s, patiente)..."
    docker run --rm --platform linux/amd64 "${MOUNTS[@]}" lotusim:focus-v2-dev bash -c '
      set +e
      source /opt/ros/jazzy/setup.bash >/dev/null 2>&1; source /lotusim_ws/install/setup.bash >/dev/null 2>&1
      export GZ_SIM_SYSTEM_PLUGIN_PATH=/lotusim_ws/install/lib GZ_SIM_RESOURCE_PATH=/lotusim_ws/src/LOTUSim/assets/models FASTDDS_BUILTIN_TRANSPORTS=DEFAULT
      chmod +x /lotusim_ws/src/LOTUSim/physics/* 2>/dev/null
      cd /lotusim_ws/src/LOTUSim/assets/models
      xdyn-for-cs focus_v2/focus_v2.yaml --address 127.0.0.1 --port 12345 --dt 0.02 -s rk4 >/tmp/x.log 2>&1 &
      sleep 4
      gz sim -s -r /lab/_offline/focus_v2_unity_round.world >/tmp/g.log 2>&1 &
      sleep 8
      python3 /lab/_offline/ctrl_course.py --world defenseScenario --sign -1 --kp 1.4 --rudmax 1.0 >/tmp/c.log 2>&1 &
      sleep 1
      timeout 100 gz topic -e -t /world/defenseScenario/dynamic_pose/info --json-output >/lab/_offline/round.poses.json 2>/dev/null
    '
    python3 "$LAB/_offline/traj_points.py"
    ;;

  run|*)
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    docker run -d --name "$NAME" --platform linux/amd64 -p 10000:10000 -e PYTHONUNBUFFERED=1 \
      "${MOUNTS[@]}" "$IMG" bash /lab/_offline/run_demo_round.sh >/dev/null
    echo "[*] backend lance, attente de l'endpoint..."
    for _ in $(seq 1 30); do
      docker logs "$NAME" 2>&1 | grep -q "Press Play in Unity" && break
      sleep 1
    done
    docker logs "$NAME" 2>&1 | tail -2
    cat <<EOF

>>> Dans Unity :
    1. Bouee (Cylinder) a Unity (0, 0, 12) = la marque que le controleur enroule
       (boucle fermee : le bateau passe a ~1.1 m, contourne et revient ; cf. _offline/CLOSED_LOOP_RECIPE.md)
    2. Play
    3. Selectionne focus_v2 + Shift+F pour le suivre
    Si focus_v2 est absent de la Hierarchy (socket zombie) :
       -> Cmd+Q Unity, rouvre la scene defenseScenario, puis relance : ./unity_demo.sh
    stop: ./unity_demo.sh stop   |   logs: ./unity_demo.sh logs   |   trajectoire: ./unity_demo.sh traj
EOF
    ;;
esac
