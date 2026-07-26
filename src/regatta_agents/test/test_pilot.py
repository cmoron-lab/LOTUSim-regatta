import math
from regatta_agents.pilot import Pilot, opt_sheet, desired_heading, wrap, CLOSE_HAULED

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


def test_waypoint_advances_and_finishes():
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, wp_radius=1.8)
    p.update(x=15.0, y=0.0, yaw=0.0, r=0.0)  # at windward mark
    assert p.wp == 1
    p.update(x=0.0, y=0.0, yaw=math.radians(180), r=0.0)  # at leeward mark
    assert p.finished is True
    assert p.rounded == 2


def test_last_mark_starts_a_new_lap_instead_of_sailing_away():
    """Rounding the last mark must re-target the first one, so she keeps racing
    round the course. With no next mark she held her downwind helm and left the
    course area for ever -- and no trim can stop her (the sail polar has no
    in-irons regime), so a new lap is the only way to keep her on the water."""
    p = Pilot(marks=[(15.0, 0.0), (0.0, 0.0)], wind_from=WF, wp_radius=1.8)
    p.update(x=15.0, y=0.0, yaw=0.0, r=0.0)
    p.update(x=0.0, y=0.0, yaw=math.radians(180), r=0.0)  # finish
    assert p.wp == 0  # windward mark again

    # heading south away from the course: she must be told to come back up
    _, helm = p.update(x=-1.0, y=0.0, yaw=math.radians(180), r=0.0)
    assert abs(helm) > math.radians(20)

    # and the second lap counts its marks on from the first
    p.update(x=15.0, y=0.0, yaw=0.0, r=0.0)
    assert (p.rounded, p.wp) == (3, 1)
