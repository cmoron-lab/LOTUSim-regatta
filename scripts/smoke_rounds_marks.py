#!/usr/bin/env python3
"""gz pose oracle: pass iff focus_v2 rounds mark_windward then mark_leeward.
Run inside a LOTUSim environment alongside gz. Usage: smoke_rounds_marks.py [timeout_sim_s]

The budget is in SIMULATED seconds. RTF then decides only how long one waits,
never the verdict -- a machine 3x faster must not hand a slowed-down boat 3x
more simulated time to pass anyway."""

import math
import sys
import time

from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node

MARKS = [
    ("windward", 0.0, 15.0),
    ("leeward", 0.0, 0.0),
]  # gz ENU positions of the buoys
WP_R = 1.8
STALL_S = 30.0  # wall seconds without a single pose before calling gz dead
state = {"idx": 0, "min": [9e9, 9e9], "x": None, "y": None, "n": 0, "sim_t": 0.0}


def on_pose(msg):
    for e in msg.pose:
        if e.name == "focus_v2":
            state["x"], state["y"], state["n"] = (
                e.position.x,
                e.position.y,
                state["n"] + 1,
            )
            state["sim_t"] = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
            for i, (_, mx, my) in enumerate(MARKS):
                d = math.hypot(mx - e.position.x, my - e.position.y)
                state["min"][i] = min(state["min"][i], d)
                if i == state["idx"] and d < WP_R:
                    state["idx"] += 1


def main():
    timeout_sim = float(sys.argv[1]) if len(sys.argv) > 1 else 130.0
    n = Node()
    n.subscribe(Pose_V, "/world/lotusim/dynamic_pose/info", on_pose)
    # The wall clock survives only as a stall detector: if gz publishes nothing,
    # sim_t never advances and the loop below would spin forever.
    seen, last_seen = 0, time.time()
    while state["sim_t"] < timeout_sim and state["idx"] < len(MARKS):
        time.sleep(0.5)
        if state["n"] > seen:
            seen, last_seen = state["n"], time.time()
        elif time.time() - last_seen > STALL_S:
            print(f"no pose for {STALL_S:.0f}s -- gz is not publishing")
            break
    print(
        f"pose msgs seen: {state['n']} | sim t: {state['sim_t']:.1f}s | last pos: "
        f"({state['x']},{state['y']})"
        if state["x"] is not None
        else "NO POSE RECEIVED"
    )
    for i, (name, _, _) in enumerate(MARKS):
        print(f"{name}: closest {state['min'][i]:.2f} m (need < {WP_R})")
    ok = state["idx"] >= len(MARKS)
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    sys.exit(0 if ok else 1)


def _selftest():
    """Feeds synthetic poses through on_pose -- no gz, no ROS. Checks the two
    things the gate gets wrong silently: reading sim time off the message, and
    counting the marks in order."""
    from types import SimpleNamespace as NS

    def pose(x, y, t):
        return NS(
            pose=[NS(name="focus_v2", position=NS(x=x, y=y, z=0.0))],
            header=NS(stamp=NS(sec=int(t), nsec=round((t % 1) * 1e9))),
        )

    state.update(
        {"idx": 0, "min": [9e9, 9e9], "x": None, "y": None, "n": 0, "sim_t": 0.0}
    )
    on_pose(pose(50.0, 50.0, 1.5))
    assert state["idx"] == 0, "a distant boat rounds nothing"
    assert abs(state["sim_t"] - 1.5) < 1e-6, "sim_t must follow the message stamp"
    on_pose(pose(*MARKS[1][1:], 2.0))
    assert state["idx"] == 0, "the leeward mark must not count before the windward one"
    on_pose(pose(*MARKS[0][1:], 3.0))
    assert state["idx"] == 1, "windward rounded"
    on_pose(pose(*MARKS[1][1:], 4.0))
    assert state["idx"] == 2, "leeward rounded, in order"
    print("selftest OK")


if __name__ == "__main__":
    main()
