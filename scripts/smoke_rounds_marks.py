#!/usr/bin/env python3
"""gz pose oracle: pass iff focus_v2 rounds mark_windward then mark_leeward.
Run INSIDE the lotusim container alongside gz. Usage: smoke_rounds_marks.py [timeout_s]"""
import math, sys, time
from gz.transport13 import Node
from gz.msgs10.pose_v_pb2 import Pose_V

MARKS = [("windward", 0.0, 15.0), ("leeward", 0.0, 0.0)]  # gz ENU positions of the buoys
WP_R = 1.8
state = {"idx": 0, "min": [9e9, 9e9], "x": None, "y": None, "n": 0}


def on_pose(msg):
    for e in msg.pose:
        if e.name == "focus_v2":
            state["x"], state["y"], state["n"] = e.position.x, e.position.y, state["n"] + 1
            for i, (_, mx, my) in enumerate(MARKS):
                d = math.hypot(mx - e.position.x, my - e.position.y)
                state["min"][i] = min(state["min"][i], d)
                if i == state["idx"] and d < WP_R:
                    state["idx"] += 1


def main():
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 130.0
    n = Node()
    n.subscribe(Pose_V, "/world/lotusim/dynamic_pose/info", on_pose)
    t0 = time.time()
    while time.time() - t0 < timeout and state["idx"] < len(MARKS):
        time.sleep(0.5)
    print(f"pose msgs seen: {state['n']} | last pos: "
          f"({state['x']},{state['y']})" if state["x"] is not None else "NO POSE RECEIVED")
    for i, (name, _, _) in enumerate(MARKS):
        print(f"{name}: closest {state['min'][i]:.2f} m (need < {WP_R})")
    ok = state["idx"] >= len(MARKS)
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
