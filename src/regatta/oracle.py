#!/usr/bin/env python3
"""Physics oracle: run the exact W/L lap the ROS helmsman will fly, directly
against xdyn over websocket (fast, deterministic). Asserts the lap completes.

This tests the SHIPPED regatta.pilot.Pilot — same brain the ROS node runs."""

import argparse
import math
import os
import sys
import textwrap
import time

from regatta import xdyn
from regatta.pilot import Pilot

# Said once, rendered twice: `-h` wraps it, the run header wraps it differently. Two
# copies would drift apart the first time the oracle's job changed.
WHAT = (
    "one lap against the physics alone -- no gz, no ROS -- to check that the shipped "
    "pilot rounds both marks. Prints ORACLE PASS or fails."
)


def _progress(pilot, st, tmax, n_marks, wall0):
    """One refreshed line, terminal only. 50 000 steps would scroll a terminal off the
    screen: a run this slow needs a heartbeat, not a history. The wall clock sits next
    to the simulated one so the reader can see the RTF for themselves -- it is shown,
    never used to decide anything (the budget is in simulated seconds)."""
    print(
        f"\r  t {st['t']:6.1f}/{tmax:.0f} s | marks {pilot.rounded}/{n_marks}"
        f" | tacks {pilot.tacks:2d} | x {st['x']:7.1f} y {st['y']:7.1f}"
        f" | {math.hypot(st['u'], st['v']):4.2f} m/s"
        f" | {time.monotonic() - wall0:4.0f} s wall",
        end="",
        flush=True,
    )


def run_lap(
    wind_dir_deg=180,
    marks=((15.0, 0.0), (0.0, 0.0)),
    dt=0.001,
    comm_dt=0.005,
    # Measured, not guessed: the lap runs 189.4 s offline (2 marks, 3 tacks), so this
    # is that plus ~30%. It is shorter than the 243 s the same lap takes through gz,
    # because the oracle starts with way on (u=0.8) rather than from rest.
    tmax=250.0,
):
    """wind_dir_deg is the yaml compass bearing the wind blows TOWARD (180 => from North).
    `dt` = xdyn internal integration step (--dt). `comm_dt` = co-sim communication step
    (Dt per websocket round-trip); xdyn substeps comm_dt internally at dt, so the two
    are independent. Override comm_dt via env COMM_DT to A/B the comm rate.
    Returns (marks_reached, tacks, trajectory)."""
    wind_from = math.radians(wind_dir_deg - 180)  # 180 blows to S -> wind_from = 0 (N)
    # Announced BEFORE xdyn is launched: launching it is itself several seconds of
    # silence, and a ten-minute run has to name the file that explains a failure
    # rather than leave the reader hunting for it.
    course = " then ".join(f"({x:.0f}, {y:.0f})" for x, y in marks)
    settings = (
        f"  xdyn rk4 --dt {dt} | comm {comm_dt} s | budget {tmax:.0f} s sim\n"
        f"  course: {course} | wind from {math.degrees(wind_from) % 360:.0f} deg\n"
        f"  xdyn log: {xdyn.XDYN_LOG}"
    )
    # One print, one flush: redirected, stdout block-buffers while stderr does not, and
    # the header would otherwise land in the log BELOW the failure it precedes.
    print(textwrap.fill(f"regatta oracle: {WHAT}", 88), settings, sep="\n", flush=True)
    xdyn.write_model(wind_dir_deg)
    xdyn.launch_xdyn(solver="rk4", dt=dt)
    try:
        sock = xdyn.ws_connect("127.0.0.1", 12345)
        pilot = Pilot(marks=list(marks), wind_from=wind_from)
        st = xdyn.init_at(wind_from + math.radians(60), u=0.8)
        traj = []
        # A redirected run keeps the header and the verdict and drops the heartbeat,
        # so no carriage return ever lands in the middle of a log file.
        live = sys.stdout.isatty()
        every = max(1, int(1.0 / comm_dt))  # one refresh per simulated second
        wall0 = time.monotonic()
        for i in range(int(tmax / comm_dt)):
            sheet, helm = pilot.update(st["x"], st["y"], xdyn.yaw_of(st), st["r"])
            st = xdyn.step(sock, st, sheet, helm, comm_dt)
            traj.append(dict(st))
            if live and i % every == 0:
                _progress(pilot, st, tmax, len(marks), wall0)
            if pilot.finished:
                break
        if live:
            print()
        return pilot.rounded, pilot.tacks, traj
    finally:
        xdyn.stop_xdyn()


def main():
    """The `regatta-oracle` entry point: one lap, asserted."""
    # argparse is here for -h and to reject a stray argument -- `regatta-oracle 400`
    # used to start a ten-minute run instead of saying it understood nothing. The two
    # knobs stay environment variables: the gz side sets them the same way.
    argparse.ArgumentParser(
        prog="regatta-oracle",
        description=WHAT,
        epilog="COMM_DT and XDYN_DT (seconds) override the co-sim and integration steps.",
    ).parse_args()
    comm_dt = float(os.environ.get("COMM_DT", 0.005))
    xdyn_dt = float(os.environ.get("XDYN_DT", 0.001))
    try:
        reached, tacks, traj = run_lap(dt=xdyn_dt, comm_dt=comm_dt)
    except RuntimeError as exc:
        # Every RuntimeError the xdyn layer raises is a diagnosed condition carrying its
        # own remedy, not a bug in this file -- a traceback would bury the one line that
        # matters, and the header above already named the log. Narrow on purpose:
        # anything else still gets its full traceback.
        print(f"\noracle failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"xdyn_dt {xdyn_dt} | comm_dt {comm_dt} | marks reached {reached}/2 "
        f"| tacks {tacks} | dur {traj[-1]['t']:.0f}s"
    )
    assert reached >= 2, f"lap incomplete: only {reached}/2 marks"
    assert tacks >= 1, f"no tack performed (tacks={tacks})"
    print("ORACLE PASS")


if __name__ == "__main__":
    sys.exit(main())
