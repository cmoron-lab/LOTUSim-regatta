#!/usr/bin/env python3
"""Offline mirror of the gz HELM_TEST probe: same setup as oracle.py (write_model(180),
init_at(wind_from + 60deg, u=0.8)) but with xdyn launched exactly like run_regatta.sh
(rk4, --dt 0.001) and constant sheet/rudder commands instead of the Pilot.

Env: HELM (deg, default 25.0), DUR (sim seconds, default 30.0)."""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__) or ".")
import ws  # noqa: E402

COMM_DT = 0.005


def main():
    wind_dir_deg = 180
    wind_from = math.radians(wind_dir_deg - 180)
    dur = float(os.environ.get("DUR", "30.0"))
    sheet = math.radians(25.0)
    helm = math.radians(float(os.environ.get("HELM", "25.0")))

    ws.write_model(wind_dir_deg)
    ws.launch_xdyn(solver="rk4", dt=0.001)
    try:
        sock = ws.ws_connect("127.0.0.1", 12345)
        st = ws.init_at(wind_from + math.radians(60), u=0.8)
        hist = []  # (t, yaw_rad)
        next_print = 0.0
        for _ in range(int(dur / COMM_DT)):
            st = ws.step(sock, st, sheet, helm, COMM_DT)
            yaw = ws.yaw_of(st)
            hist.append((st["t"], yaw))
            if st["t"] >= next_print:
                print(
                    f"t={st['t']:.1f} yaw_ned={math.degrees(yaw):.1f}deg "
                    f"r={st['r']:.4f}rad/s u={st['u']:.3f}m/s v={st['v']:.3f}m/s"
                )
                next_print += 2.0

        final_t, final_yaw = hist[-1]
        window = [y for t, y in hist if t >= final_t - 5.0]
        # circular mean (headings wrap at +-180deg)
        mean_yaw = math.atan2(
            sum(math.sin(y) for y in window) / len(window),
            sum(math.cos(y) for y in window) / len(window),
        )
        print(
            f"final cap={math.degrees(final_yaw):.1f}deg | "
            f"mean cap (last 5s)={math.degrees(mean_yaw):.1f}deg"
        )
    finally:
        ws.stop_xdyn()


if __name__ == "__main__":
    main()
