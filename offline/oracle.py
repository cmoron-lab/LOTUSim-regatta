#!/usr/bin/env python3
"""Physics oracle: run the exact W/L lap the ROS helmsman will fly, directly
against xdyn over websocket (fast, deterministic). Asserts the lap completes.

This tests the SHIPPED regatta_agents.pilot.Pilot — same brain the ROS node runs."""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__) or ".")
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src", "regatta_agents")
)
from regatta_agents.pilot import Pilot  # noqa: E402
import ws  # noqa: E402


def run_lap(
    wind_dir_deg=180,
    marks=((15.0, 0.0), (0.0, 0.0)),
    dt=0.001,
    comm_dt=0.005,
    tmax=170.0,
):
    """wind_dir_deg is the yaml compass bearing the wind blows TOWARD (180 => from North).
    `dt` = xdyn internal integration step (--dt). `comm_dt` = co-sim communication step
    (Dt per websocket round-trip); xdyn substeps comm_dt internally at dt, so the two
    are independent. Override comm_dt via env COMM_DT to A/B the comm rate.
    Returns (marks_reached, tacks, trajectory)."""
    wind_from = math.radians(wind_dir_deg - 180)  # 180 blows to S -> wind_from = 0 (N)
    ws.write_model(wind_dir_deg)
    ws.launch_xdyn(solver="rk4", dt=dt)
    try:
        sock = ws.ws_connect("127.0.0.1", 12345)
        pilot = Pilot(marks=list(marks), wind_from=wind_from)
        st = ws.init_at(wind_from + math.radians(60), u=0.8)
        traj = []
        for _ in range(int(tmax / comm_dt)):
            sheet, helm = pilot.update(st["x"], st["y"], ws.yaw_of(st), st["r"])
            st = ws.step(sock, st, sheet, helm, comm_dt)
            traj.append(dict(st))
            if pilot.finished:
                break
        return pilot.rounded, pilot.tacks, traj
    finally:
        ws.stop_xdyn()


if __name__ == "__main__":
    comm_dt = float(os.environ.get("COMM_DT", 0.005))
    xdyn_dt = float(os.environ.get("XDYN_DT", 0.001))
    reached, tacks, traj = run_lap(dt=xdyn_dt, comm_dt=comm_dt)
    print(
        f"xdyn_dt {xdyn_dt} | comm_dt {comm_dt} | marks reached {reached}/2 "
        f"| tacks {tacks} | dur {traj[-1]['t']:.0f}s"
    )
    assert reached >= 2, f"lap incomplete: only {reached}/2 marks"
    assert tacks >= 1, f"no tack performed (tacks={tacks})"
    print("ORACLE PASS")
