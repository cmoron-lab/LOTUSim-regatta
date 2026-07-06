# Copyright (c) 2026 Cyril Moron — EPL-2.0
"""Pure windward-leeward control brain for the Focus V2, shared by the offline
xdyn oracle and the ROS2 helmsman. No I/O: feed it pose, get (sheet, helm).

Ported from the offline-validated _offline/cosim.py (2/2 marks, 3-4 tacks on the
tuned model). All angles radians; headings are NED compass; HELM_SIGN=-1."""
import math

HELM_SIGN = -1.0
AOA_OPT = 20.0
NO_GO = math.radians(50.0)          # half dead-zone: mark closer than this to the wind -> beat
CLOSE_HAULED = math.radians(60.0)   # real upwind heading (tenable + good VMG; foot for speed)
KP, KD, HELM_MAX = 2.2, 0.9, math.radians(35)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def opt_sheet(twa_deg):
    """Sheet angle (rad) vs true-wind angle. Hard upwind, eased downwind — calibrated
    on the patched-xdyn beat sweep; over-easing upwind kills drive (crawl + leeway)."""
    return math.radians(clamp(0.6 * (twa_deg - 42.0), 4.0, 80.0))


def desired_heading(pos, mark, wind_from, tack):
    """Target heading: mark inside the no-go cone -> close-hauled on the current
    tack (+1/-1); else steer straight at the mark."""
    brg = math.atan2(mark[1] - pos[1], mark[0] - pos[0])
    if abs(wrap(brg - wind_from)) < NO_GO:
        return wrap(wind_from + tack * CLOSE_HAULED)
    return brg


def cross_track(pos, a, b):
    """Signed perpendicular offset of pos from line a->b (>0 = left of a->b)."""
    lx, ly = b[0] - a[0], b[1] - a[1]
    L = math.hypot(lx, ly) or 1.0
    return ((pos[0] - a[0]) * (-ly) + (pos[1] - a[1]) * lx) / L


class Pilot:
    """Stateful W/L pilot. update(x,y,yaw,r) -> (sheet_rad, helm_rad).

    State machine: beat toward the windward mark on alternating tacks inside a
    corridor; when crossing the corridor edge, run an ENGAGED-TACK (firm rudder +
    high gain) through the eye instead of stalling in irons; steer straight when
    the mark is not upwind; advance to the next mark within wp_radius."""

    def __init__(self, marks, wind_from, corridor=5.0, wp_radius=1.8):
        self.marks = list(marks)
        self.wind_from = wind_from
        self.corridor = corridor
        self.wp_radius = wp_radius
        self.wp = 0
        self.tack = 1
        self.tacks = 0
        self.leg_start = (0.0, 0.0)
        self.tacking = False
        self.finished = False

    def update(self, x, y, yaw, r):
        pos = (x, y)
        if self.finished:
            return opt_sheet(abs(math.degrees(wrap(yaw - self.wind_from)))), 0.0
        mark = self.marks[self.wp]
        if math.hypot(mark[0] - x, mark[1] - y) < self.wp_radius:
            self.wp += 1
            if self.wp >= len(self.marks):
                self.finished = True
                return opt_sheet(abs(math.degrees(wrap(yaw - self.wind_from)))), 0.0
            self.leg_start, mark, self.tacking = pos, self.marks[self.wp], False

        brg = math.atan2(mark[1] - y, mark[0] - x)
        upwind = abs(wrap(brg - self.wind_from)) < NO_GO

        if self.tacking:
            desired = wrap(self.wind_from + self.tack * CLOSE_HAULED)
            if abs(wrap(desired - yaw)) < math.radians(18):
                self.tacking = False
        else:
            if upwind:
                c = cross_track(pos, self.leg_start, mark)
                if (c > self.corridor and self.tack > 0) or (c < -self.corridor and self.tack < 0):
                    self.tack, self.tacks, self.tacking = -self.tack, self.tacks + 1, True
            desired = desired_heading(pos, mark, self.wind_from, self.tack)

        kp = KP * (2.4 if self.tacking else 1.0)
        helm = clamp(HELM_SIGN * (kp * wrap(desired - yaw) - KD * r), -HELM_MAX, HELM_MAX)
        twa = abs(math.degrees(wrap(yaw - self.wind_from)))
        return opt_sheet(twa), helm
