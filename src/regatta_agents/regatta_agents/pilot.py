# Copyright (c) 2026 Cyril Moron — EPL-2.0
"""Pure windward-leeward control brain for the Focus V2, shared by the offline
xdyn oracle and the ROS2 helmsman. No I/O: feed it pose, get (sheet, helm).

Ported from the offline-validated _offline/cosim.py (2/2 marks, 3-4 tacks on the
tuned model). All angles radians; headings are NED compass; HELM_SIGN=-1."""

import math

HELM_SIGN = -1.0
AOA_OPT = 20.0
# half dead-zone: a mark closer than this to the wind has to be beaten to
NO_GO = math.radians(50.0)
# real upwind heading (tenable + good VMG; foot for speed)
CLOSE_HAULED = math.radians(60.0)
KP, KD, HELM_MAX = 2.2, 0.9, math.radians(35)
# how far to the side of a buoy the pilot aims, so it sails AROUND it: the boat is
# 1 m long and the buoy has girth, so anything less is a collision course
ROUND_OFFSET = 2.0


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


def leg_axis(a, b):
    """Unit vector from a to b; (1,0) if they coincide."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L) if L else (1.0, 0.0)


def rounding_target(leg_start, mark, offset=ROUND_OFFSET, clearance=ROUND_OFFSET):
    """Point to steer at so the mark gets ROUNDED rather than hit: `offset` to the
    boat's starboard of the leg axis, so the mark is left to port (the World Sailing
    convention for a W/L course), and `clearance` BEYOND it along the leg, so she
    sails clear before turning. In NED (x North, y East) the starboard of a heading
    (ux, uy) is (-uy, ux).

    Both components matter. Aiming abeam of the mark and demanding she then get
    clear of it cannot work: past the mark the target lies astern, so the pilot
    would turn her back south onto it and she would circle the target instead of
    the mark. The point she steers at has to BE the point that clears it."""
    ux, uy = leg_axis(leg_start, mark)
    return (
        mark[0] + ux * clearance - uy * offset,
        mark[1] + uy * clearance + ux * offset,
    )


def has_rounded(pos, mark, leg_start, clearance=ROUND_OFFSET):
    """True once the mark is CLEAR astern along the leg AND was left to port.

    A distance threshold cannot express a rounding: it fires short of the mark, so
    the boat cuts the corner and never passes it -- visible in the web UI as a boat
    that stays south of the windward buoy. Off on the wrong side it stays False and
    the pilot keeps steering at the offset target, which brings her back round.

    `clearance` is why she visibly sails ROUND the buoy instead of pivoting on its
    latitude. Turning the instant she crosses it left her only 5-86 cm past the mark
    depending on the run -- geometrically a rounding, indistinguishable from a corner
    cut on screen. Sailing clear first also makes the turn a proper arc, so where the
    turn ends no longer depends on how the helm's 30 Hz timer lines up with the
    physics clock."""
    ux, uy = leg_axis(leg_start, mark)
    dx, dy = pos[0] - mark[0], pos[1] - mark[1]
    astern = dx * ux + dy * uy >= clearance
    to_starboard = -dx * uy + dy * ux > 0.0  # mark on the boat's port hand
    return astern and to_starboard


class Pilot:
    """Stateful W/L pilot. update(x,y,yaw,r) -> (sheet_rad, helm_rad).

    State machine: beat toward the windward mark on alternating tacks inside a
    corridor; when crossing the corridor edge, run an ENGAGED-TACK (firm rudder +
    high gain) through the eye instead of stalling in irons; steer straight when
    the mark is not upwind; aim ROUND_OFFSET to the side of each mark and count it
    once it is astern and left to port; round the last mark and start the next lap.

    The leeward mark doubles as the start and finish line: crossing its
    perpendicular southbound IS the finish, so no extra geometry is needed."""

    def __init__(self, marks, wind_from, corridor=5.0):
        self.marks = list(marks)
        self.wind_from = wind_from
        self.corridor = corridor
        self.wp = 0
        self.rounded = 0  # marks rounded since the start, across laps
        self.tack = 1
        self.tacks = 0
        self.leg_start = (0.0, 0.0)
        self.tacking = False
        self.finished = False  # latched once a full lap is in: the gates stop there

    def _steer(self, desired, yaw, r, gain=1.0):
        """Sheet for the current true-wind angle, PD rudder onto `desired`."""
        helm = clamp(
            HELM_SIGN * (gain * KP * wrap(desired - yaw) - KD * r), -HELM_MAX, HELM_MAX
        )
        return opt_sheet(abs(math.degrees(wrap(yaw - self.wind_from)))), helm

    def update(self, x, y, yaw, r):
        pos = (x, y)
        mark = self.marks[self.wp]
        # Rounding the last mark starts a new lap rather than stopping: this xdyn sail
        # polar has no in-irons regime (Cl = 0.8 at 10 deg of incidence, no stall), so
        # NO trim brings her to rest -- measured, see docs/measurements/2026-07-WSL.md.
        # Sailing on is what keeps her on the course area; centring the helm at the
        # last mark sailed her out of it for ever, which is what the web UI showed.
        if has_rounded(pos, mark, self.leg_start):
            self.rounded += 1
            self.wp = (self.wp + 1) % len(self.marks)
            if self.wp == 0:
                self.finished = True
            self.leg_start, mark, self.tacking = pos, self.marks[self.wp], False

        # Steer at a point beside the mark, never at the mark itself.
        target = rounding_target(self.leg_start, mark)
        brg = math.atan2(target[1] - y, target[0] - x)
        upwind = abs(wrap(brg - self.wind_from)) < NO_GO

        if self.tacking:
            desired = wrap(self.wind_from + self.tack * CLOSE_HAULED)
            if abs(wrap(desired - yaw)) < math.radians(18):
                self.tacking = False
        else:
            if upwind:
                c = cross_track(pos, self.leg_start, target)
                if (c > self.corridor and self.tack > 0) or (
                    c < -self.corridor and self.tack < 0
                ):
                    self.tack, self.tacks, self.tacking = (
                        -self.tack,
                        self.tacks + 1,
                        True,
                    )
            desired = desired_heading(pos, target, self.wind_from, self.tack)

        return self._steer(desired, yaw, r, gain=2.4 if self.tacking else 1.0)
