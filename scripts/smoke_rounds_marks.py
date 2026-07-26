#!/usr/bin/env python3
"""gz pose oracle: pass iff focus_v2 rounds mark_windward then mark_leeward.
Run inside a LOTUSim environment alongside gz. Usage: smoke_rounds_marks.py [timeout_sim_s]

The budget is in SIMULATED seconds. RTF then decides only how long one waits,
never the verdict -- a machine 3x faster must not hand a slowed-down boat 3x
more simulated time to pass anyway."""

import sys
import time

from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node

# gz ENU positions of the buoys (x = East, y = North), then how a rounding is
# judged. The course axis is North-South, so "the mark is astern" is a test on y
# and "the mark was left to port" a test on x -- no need for the general vector
# form the pilot uses. Signs: beating North the buoy must end up West of the boat
# (x > 0), running South it must end up East of her (x < 0).
MARKS = [
    ("windward", 0.0, 15.0, +1, +1),
    ("leeward", 0.0, 0.0, -1, -1),
]
# The rules put no ceiling on how wide a mark may be left, but a gate must: the
# pilot aims ROUND_OFFSET = 2 m off inside a +-5 m corridor, so a pass wider than
# this did not sail the leg. Loose on purpose -- the old criterion passed by 4 cm.
MAX_SIDE = 8.0
STALL_S = 30.0  # wall seconds without a single pose before calling gz dead
state = {"idx": 0, "side": [None, None], "x": None, "y": None, "n": 0, "sim_t": 0.0}


def on_pose(msg):
    for e in msg.pose:
        if e.name == "focus_v2":
            state["x"], state["y"], state["n"] = (
                e.position.x,
                e.position.y,
                state["n"] + 1,
            )
            state["sim_t"] = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
            i = state["idx"]
            if i < len(MARKS):
                _, mx, my, along_sign, side_sign = MARKS[i]
                # A distance test would pass on a corner cut: 1.58 m from the buoy
                # while still short of it is not a rounding, and it is what the web
                # UI showed. Demand that the buoy end up astern AND on the port hand.
                astern = along_sign * (e.position.y - my) >= 0.0
                side = side_sign * (e.position.x - mx)
                if astern and 0.0 < side <= MAX_SIDE:
                    state["side"][i] = side
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
    for i, (name, *_) in enumerate(MARKS):
        s = state["side"][i]
        print(
            f"{name}: rounded, left to port by {s:.2f} m"
            if s is not None
            else f"{name}: NOT rounded (never astern with the buoy to port)"
        )
    ok = state["idx"] >= len(MARKS)
    print("SMOKE PASS" if ok else "SMOKE FAIL")
    sys.exit(0 if ok else 1)


def _selftest():
    """Feeds synthetic poses through on_pose -- no gz, no ROS. Checks the things
    the gate gets wrong silently: reading sim time off the message, counting the
    marks in order, and calling a corner cut a rounding."""
    from types import SimpleNamespace as NS

    def pose(x, y, t):
        return NS(
            pose=[NS(name="focus_v2", position=NS(x=x, y=y, z=0.0))],
            header=NS(stamp=NS(sec=int(t), nsec=round((t % 1) * 1e9))),
        )

    state.update(
        {"idx": 0, "side": [None, None], "x": None, "y": None, "n": 0, "sim_t": 0.0}
    )
    on_pose(pose(50.0, 50.0, 1.5))
    assert state["idx"] == 0, "a distant boat rounds nothing"
    assert abs(state["sim_t"] - 1.5) < 1e-6, "sim_t must follow the message stamp"
    on_pose(pose(0.0, 0.0, 2.0))
    assert state["idx"] == 0, "the leeward mark must not count before the windward one"
    on_pose(pose(0.5, 13.5, 2.5))
    assert state["idx"] == 0, "1.58 m from the buoy but short of it is a corner cut"
    on_pose(pose(-2.0, 15.5, 2.8))
    assert state["idx"] == 0, "past the buoy but on the wrong side is not a rounding"
    on_pose(pose(2.0, 15.5, 3.0))
    assert state["idx"] == 1, "windward rounded, buoy left to port"
    on_pose(pose(-1.0, -1.0, 4.0))
    assert state["idx"] == 2, "leeward rounded, in order"
    assert state["side"] == [2.0, 1.0], (
        "the lateral pass distance is what gets reported"
    )
    print("selftest OK")


if __name__ == "__main__":
    main()
