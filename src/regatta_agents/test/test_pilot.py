import math
from regatta_agents.pilot import (
    CLOSE_HAULED,
    ROUND_OFFSET,
    Pilot,
    desired_heading,
    has_rounded,
    opt_sheet,
    rounding_target,
    wrap,
)

WF = 0.0  # wind from North


def test_opt_sheet_hard_upwind_eased_downwind():
    assert math.degrees(opt_sheet(45)) < 10  # close-hauled: sheet hard in
    assert math.degrees(opt_sheet(150)) > 60  # downwind: eased out
    assert 4.0 <= math.degrees(opt_sheet(0)) <= 4.01  # clamped floor


def test_desired_heading_direct_when_mark_not_upwind():
    # mark abeam/downwind of the wind axis -> steer straight at it
    d = desired_heading((0, 0), (0, 10), WF, tack=1)  # bearing due East(y+) = +pi/2
    assert abs(wrap(d - math.pi / 2)) < 1e-6


def test_desired_heading_close_hauled_when_mark_dead_upwind():
    # mark dead upwind (North, x+) is inside the no-go cone -> beat on the tack
    d = desired_heading((0, 0), (10, 0), WF, tack=1)
    assert abs(wrap(d - (WF + CLOSE_HAULED))) < 1e-6


def test_tack_flips_and_counts_when_crossing_corridor():
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, corridor=5.0)
    # beating on starboard (tack=+1); push the boat well left of the leg line
    p.update(x=3.0, y=6.0, yaw=math.radians(-60), r=0.0)  # y=6 > corridor 5
    assert p.tacks == 1
    assert p.tacking is True
    assert p.tack == -1


def test_high_gain_helm_while_tacking():
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, corridor=5.0)
    p.update(x=3.0, y=6.0, yaw=math.radians(-60), r=0.0)  # enters tacking (target -60)
    # boat still on the old tack heading (+60), mid-turn through the eye -> hard helm
    _, helm_tacking = p.update(x=3.1, y=6.0, yaw=math.radians(60), r=0.0)
    assert abs(helm_tacking) > 0.0  # commanding a turn through the eye


def test_rounding_target_sits_beside_the_mark_on_the_port_hand():
    # leg due North (NED x): the mark ends up on the boat's PORT hand, so the point
    # she steers at is ROUND_OFFSET East (y+) of it and ROUND_OFFSET beyond (x+)
    tx, ty = rounding_target((0.0, 0.0), (15.0, 0.0))
    assert (tx, ty) == (15.0 + ROUND_OFFSET, ROUND_OFFSET)
    # leg due South, coming back down: both components flip with the axis
    tx, ty = rounding_target((15.0, 0.0), (0.0, 0.0))
    assert (tx, ty) == (-ROUND_OFFSET, -ROUND_OFFSET)

    # the target must itself satisfy the rounding test, or the pilot would be sent
    # to a point that never counts and she would circle it for ever
    assert has_rounded(
        rounding_target((0.0, 0.0), (15.0, 0.0)), (15.0, 0.0), (0.0, 0.0)
    )


def test_mark_counts_only_once_clear_astern_and_left_to_port():
    leg, mark = (0.0, 0.0), (15.0, 0.0)  # beating North to the windward mark
    # THE bug the web UI showed: 1.58 m from the buoy is inside the old 1.8 m
    # radius, yet she is still short of it -- that is a corner cut, not a rounding
    assert not has_rounded((13.5, 0.5), mark, leg)
    # level with the buoy is not clear of it either: turning here left her 5 cm past
    assert not has_rounded((15.1, 2.0), mark, leg)
    assert not has_rounded((19.0, -2.0), mark, leg)  # clear astern, wrong side
    assert has_rounded((17.5, 2.0), mark, leg)  # clear by ROUND_OFFSET, buoy to port


def test_lap_completes_by_passing_both_marks_and_then_starts_a_new_one():
    """Rounding the last mark must re-target the first one, so she keeps racing
    round the course. With no next mark she held her downwind helm and left the
    course area for ever -- and no trim can stop her (the sail polar has no
    in-irons regime), so a new lap is the only way to keep her on the water."""
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF)
    p.update(x=13.5, y=0.5, yaw=0.0, r=0.0)  # close to the buoy but short of it
    assert (p.wp, p.rounded) == (0, 0)
    p.update(x=17.5, y=2.0, yaw=0.0, r=0.0)  # clear past it, leaving it to port
    assert (p.wp, p.rounded) == (1, 1)

    p.update(x=-2.5, y=-2.0, yaw=math.radians(180), r=0.0)  # clear across the finish
    assert p.finished is True
    assert (p.wp, p.rounded) == (0, 2)  # windward mark again: lap two

    # heading south away from the course: she must be told to come back up
    _, helm = p.update(x=-3.0, y=-2.0, yaw=math.radians(180), r=0.0)
    assert abs(helm) > math.radians(20)

    # and the second lap counts its marks on from the first
    p.update(x=17.5, y=2.0, yaw=0.0, r=0.0)
    assert (p.rounded, p.wp) == (3, 1)
